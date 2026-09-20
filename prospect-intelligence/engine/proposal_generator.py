"""
Proposal Draft Generator for Coextend Prospect Intelligence.
Generates tailored scope-of-work proposals grounded in 08 - Proposal Templates.docx,
02 - Services.docx, and 03 - Company Capabilities.docx.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from api.models import EvidenceLabel, Finding, ProposalDraft, ResearchBrief
from config import settings
from knowledge.retrieval import format_chunks_for_prompt, retrieve_batch
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_GENAI_CLIENT: genai.Client | None = None

def _get_genai_client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        _GENAI_CLIENT = genai.Client(api_key=settings.gemini_api_key)
    return _GENAI_CLIENT

_PROPOSAL_SCHEMA = {
    "type": "object",
    "properties": {
        "proposal_title": {"type": "string", "description": "Title of the proposal"},
        "client_requirement": {"type": "string", "description": "Context and need summary"},
        "proposed_scope": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of scoped services (BIM drafting, takeoffs, estimating, etc.)",
        },
        "deliverables": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of explicit deliverables, file formats, and schedules",
        },
        "turnaround_programme": {"type": "string", "description": "Turnaround times and milestone workflow"},
        "commercial_options": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "option_name": {"type": "string"},
                    "description": {"type": "string"},
                    "basis": {"type": "string"},
                },
                "required": ["option_name", "description", "basis"],
            },
            "description": "3 standard engagement models: Project Package, Hourly Resource, Monthly Retainer",
        },
        "assumptions_exclusions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technical assumptions and boundaries",
        },
        "pilot_option": {"type": "string", "description": "Low-risk pilot offer to validate workflow and quality"},
    },
    "required": [
        "proposal_title",
        "client_requirement",
        "proposed_scope",
        "deliverables",
        "turnaround_programme",
        "commercial_options",
        "assumptions_exclusions",
        "pilot_option",
    ],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """\
You are drafting a technical service proposal for Coextend Global LLP for a façade / cladding contractor.

Structure the proposal strictly following Coextend's Proposal Template (08 - Proposal Templates.docx):
1. Proposal Title: Clear reference to the prospect and service focus.
2. Client Requirement: Summarize their observed trade focus, projects, and capacity/estimating bottleneck.
3. Proposed Scope: Bulleted items (e.g. Quantity Take-Off, BOQ, Revit BIM Shop Drawings, Remedial Cladding Packages).
4. Deliverables: Formats (.rvt, .dwg, .xlsx BOQ), revisions, and turnaround.
5. Turnaround Programme: Fast turnaround workflows (e.g. 48-72 hr for takeoffs, dedicated sprint milestones).
6. Commercial Options:
   - Option 1: Project Package (Fixed fee per tender/project scope)
   - Option 2: Hourly On-Demand Resource (Flexible hourly rate for overflow)
   - Option 3: Dedicated Monthly Retainer (Dedicated full-time estimator/draftsman team)
7. Assumptions & Exclusions: Engineering certification boundaries, client input drawing quality, software access.
8. Pilot Option: Small defined pilot project (e.g. 1 package takeoff or 1 shop drawing set) to demonstrate QA and delivery before long-term commitment.

AI RULES:
- Ground all facts in Verified/Probable prospect findings.
- Do NOT invent specific contract prices (use bracketed placeholders like [£ / Fixed Fee] or [Standard Tier Rate]).
- Do NOT promise statutory engineering sign-off.
- Return ONLY valid JSON matching the schema.
"""


def _normalize_str_list(val: Any) -> list[str]:
    if isinstance(val, list):
        out = []
        for item in val:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(", ".join(f"{k}: {v}" for k, v in item.items()))
            else:
                out.append(str(item))
        return out
    elif isinstance(val, dict):
        return [f"{k}: {v}" for k, v in val.items()]
    elif isinstance(val, str):
        return [val]
    return []


def _normalize_dict_list(val: Any) -> list[dict]:
    if isinstance(val, list):
        out = []
        for item in val:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str):
                out.append({"option_name": "Option", "description": item, "basis": "TBD"})
            else:
                out.append({"value": str(item)})
        return out
    elif isinstance(val, dict):
        return [val]
    return []


async def generate_proposal_draft(brief: ResearchBrief) -> ProposalDraft:
    """Generate a founder-ready proposal draft tailored to the prospect."""
    logger.info("Proposal draft generation start", extra={"job_id": brief.job_id})

    # Retrieve proposal and capability templates in a single batch
    kb_queries = [
        "Proposal template scope of work deliverables commercial options",
        "Façade BIM drafting takeoffs estimating commercial models",
        "Pilot project trial workflow Coextend capabilities",
    ]
    unique_chunks = await retrieve_batch(kb_queries, top_k=3)
    kb_text = format_chunks_for_prompt(unique_chunks[:6]) if unique_chunks else "(Standard Coextend Proposal Templates)"

    # Format findings
    safe_findings = [
        f"  [{f.label.value}] {f.field}: {f.value}"
        for f in (brief.projects_signals + brief.likely_requirements)
        if f.label in (EvidenceLabel.VERIFIED, EvidenceLabel.PROBABLE)
    ]
    company_name = brief.snapshot.get("company_name", "Prospective Client")
    contact_name = brief.contact.get("name") or "Leadership Team"
    contact_title = brief.contact.get("title", "")

    user_content = (
        f"Client: {company_name}\n"
        f"Contact: {contact_name} ({contact_title})\n"
        f"Sector: {brief.snapshot.get('sector', 'Building Envelope Contractor')}\n"
        f"Location: {brief.snapshot.get('location', 'UK/US')}\n"
        f"Recommended Approach: {brief.recommended_approach.summary}\n"
        f"Key Offerings: {', '.join(brief.recommended_approach.key_capabilities_to_lead_with)}\n\n"
        f"Verified Findings:\n" + "\n".join(safe_findings) + f"\n\n"
        f"Internal Knowledge & Templates:\n{kb_text}"
    )

    client = _get_genai_client()
    full_prompt = _SYSTEM_PROMPT + "\n\n" + user_content

    _PROPOSAL_LLM_TIMEOUT = 25.0
    raw = {}
    for attempt in range(2):
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda p=full_prompt: client.models.generate_content(
                        model=settings.gemini_llm_model,
                        contents=p,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.3,
                        ),
                    ),
                ),
                timeout=_PROPOSAL_LLM_TIMEOUT,
            )
            raw = json.loads(response.text)
            if isinstance(raw, list) and raw:
                raw = raw[0]
            break
        except asyncio.TimeoutError:
            logger.warning("Gemini proposal LLM call timed out after %ds (attempt %d)", _PROPOSAL_LLM_TIMEOUT, attempt + 1)
            if attempt == 1:
                raise RuntimeError(f"failed:timeout (Proposal generation timed out after {_PROPOSAL_LLM_TIMEOUT}s)")
        except Exception as exc:
            exc_str = str(exc)
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                raise RuntimeError(f"failed:rate_limited (Proposal generation API rate limited: {exc})") from exc
            if any(k in exc_str.lower() for k in ("api key not valid", "api_key_invalid", "invalid_argument")):
                logger.warning("Proposal LLM API key error; generating template proposal directly.")
                raw = {
                    "proposal_title": f"Pre-Construction Technical Services Proposal — {company_name}",
                    "client_requirement": f"Support for {company_name} to alleviate estimating and drafting capacity bottlenecks during peak tendering cycles.",
                    "proposed_scope": [
                        "Quantity take-offs and material bills of quantities (BOQ)",
                        "Revit BIM 3D modeling and facade interface coordination",
                        "2D CAD shop drawings, fabrication packs, and bracketry details",
                    ],
                    "deliverables": [
                        "Complete Excel BOQ with detailed measurement breakdown",
                        "Coordinated BIM model (.rvt) and CAD drawings (.dwg, .pdf)",
                        "Two rounds of revisions per milestone submission",
                    ],
                    "turnaround_programme": "Takeoffs: 48-72 hours. Shop drawings: 5-7 working days. Dedicated sprint reviews.",
                    "commercial_options": [
                        {"option_name": "Project Package", "description": "Fixed fee milestone delivery per tender package", "basis": "[Fixed Package Fee]"},
                        {"option_name": "Hourly On-Demand", "description": "Flexible capacity support for urgent tender spikes", "basis": "[Hourly Rate]"},
                        {"option_name": "Monthly Dedicated Team", "description": "Full-time dedicated pre-construction engineer", "basis": "[Monthly Retainer]"},
                    ],
                    "assumptions_exclusions": [
                        "Client to provide architectural drawings and project specifications.",
                        "Statutory structural engineering sign-off excluded unless agreed in writing.",
                        "Standard turnaround based on agreed milestone schedule.",
                    ],
                    "pilot_option": "Single tender takeoff or single shop drawing package (up to 40 hours) to demonstrate quality and turnaround before long-term commitment.",
                }
                break
            if attempt == 0:
                full_prompt += f"\n\nJSON error: {exc}. Return valid JSON only."
            else:
                raise RuntimeError(f"Proposal generation LLM error: {exc}") from exc

    # Render Markdown
    props_scope = _normalize_str_list(raw.get("proposed_scope") or raw.get("scope_of_work") or raw.get("scope") or [])
    delivs = _normalize_str_list(raw.get("deliverables") or raw.get("key_deliverables") or [])
    comm_opts = _normalize_dict_list(raw.get("commercial_options") or raw.get("commercial_models") or raw.get("pricing_options") or [])
    assumptions = _normalize_str_list(
        raw.get("assumptions_exclusions")
        or raw.get("assumptions_and_exclusions")
        or raw.get("assumptions")
        or raw.get("exclusions")
        or []
    )
    if not assumptions:
        assumptions = [
            "Client to provide clear architectural drawing packages, structural inputs, and specifications.",
            "Statutory engineering calculations and certified sign-off excluded unless explicitly agreed in writing.",
            "Standard delivery covers up to 2 rounds of review revisions per milestone.",
        ]
    if not props_scope:
        props_scope = ["Façade takeoffs, BOQ preparation, and 2D/3D draughting support."]
    if not delivs:
        delivs = ["Full drawing package (.dwg / .rvt) and Excel BOQ."]
    if not comm_opts:
        comm_opts = [
            {"option_name": "Project Package", "description": "Fixed fee milestone delivery", "basis": "[Fixed Package Fee]"},
            {"option_name": "Hourly On-Demand", "description": "Flexible capacity support", "basis": "[Hourly Rate]"},
            {"option_name": "Monthly Retainer", "description": "Dedicated estimator / CAD technician", "basis": "[Monthly Retainer]"},
        ]

    raw_normalized = dict(raw)
    raw_normalized["proposed_scope"] = props_scope
    raw_normalized["deliverables"] = delivs
    raw_normalized["commercial_options"] = comm_opts
    raw_normalized["assumptions_exclusions"] = assumptions

    rendered_md = _render_proposal_markdown(company_name, raw_normalized)

    return ProposalDraft(
        job_id=brief.job_id,
        proposal_title=str(raw.get("proposal_title", f"Technical Services Proposal — {company_name}")),
        client_requirement=str(raw.get("client_requirement", "")),
        proposed_scope=props_scope,
        deliverables=delivs,
        turnaround_programme=str(raw.get("turnaround_programme", "")),
        commercial_options=comm_opts,
        assumptions_exclusions=assumptions,
        pilot_option=str(raw.get("pilot_option", "")),
        rendered_markdown=rendered_md,
        status="draft",
        generated_at=datetime.now(UTC),
    )


def _render_proposal_markdown(company_name: str, p: dict) -> str:
    now_str = datetime.now(UTC).strftime("%d %B %Y")
    lines = [
        f"# {p.get('proposal_title', f'Technical Services Proposal — {company_name}')}",
        f"**Client:** {company_name}  |  **Prepared by:** Coextend Global LLP  |  **Date:** {now_str}",
        "**Status:** Draft — For Human Review & Commercial Approval",
        "",
        "---",
        "",
        "## 1. Client Requirement & Project Context",
        str(p.get("client_requirement", "Capacity support for façade estimating and technical drafting.")),
        "",
        "## 2. Proposed Scope of Services",
    ]
    for item in p.get("proposed_scope", []):
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## 3. Deliverables & Documentation",
    ])
    for d in p.get("deliverables", []):
        lines.append(f"- {d}")
    lines.extend([
        "",
        "## 4. Programme & Turnaround Schedule",
        str(p.get("turnaround_programme", "Fast-track delivery with milestone reviews.")),
        "",
        "## 5. Commercial Engagement Options",
        "| Option | Description | Commercial Basis |",
        "| :--- | :--- | :--- |",
    ])
    for opt in p.get("commercial_options", []):
        if isinstance(opt, dict):
            name = opt.get("option_name") or opt.get("name") or "Option"
            desc = opt.get("description") or opt.get("scope") or ""
            basis = opt.get("basis") or opt.get("pricing") or "[Fixed / Hourly / Retainer]"
            lines.append(f"| **{name}** | {desc} | {basis} |")
        else:
            lines.append(f"| **Option** | {opt} | TBD |")

    lines.extend([
        "",
        "## 6. Assumptions & Technical Boundaries",
    ])
    for a in p.get("assumptions_exclusions", []):
        lines.append(f"- {a}")
    lines.extend([
        "",
        "## 7. Quality Assurance & Communication",
        "- Multi-tier checking protocol by Senior Façade Engineers prior to delivery.",
        "- Dedicated Slack/Teams channel and weekly progress standups.",
        "- Revision control and ISO-aligned document naming conventions.",
        "",
        "## 8. Low-Risk Pilot Proposal",
        str(p.get("pilot_option", "We invite you to start with a single defined pilot project to validate quality and turnaround.")),
        "",
        "---",
        "*(Proposal generated by Coextend Prospect Intelligence MVP — internal draft for review)*",
    ])
    return "\n".join(str(l) for l in lines)
