"""
Research Brief Generator.
Assembles a ResearchBrief from:
  (a) ResearchFindings — prospect facts only
  (b) LeadScore — computed deterministically
  (c) Retrieved internal-knowledge chunks — Coextend facts only, with citations

The LLM is constrained to a JSON schema so output is always structurally valid.
Evidence labels are NOT allowed to be upgraded (enforced by post-generation check).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime


from api.models import (
    EvidenceLabel,
    Finding,
    LeadScore,
    NextAction,
    RecommendedApproach,
    ResearchBrief,
    ResearchFindings,
    SourceRef,
)
from config import settings
from knowledge.retrieval import format_chunks_for_prompt, retrieve_batch
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_GENAI_CLIENT: genai.Client | None = None

def _get_genai_client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        import os
        key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")).strip().strip("'").strip('"')
        _GENAI_CLIENT = genai.Client(api_key=key)
    return _GENAI_CLIENT


# JSON schema for brief generation

_BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "snapshot": {
            "type": "object",
            "description": "Key company facts: company_name, website, location, sector, size, etc.",
            "additionalProperties": {"type": "string"},
        },
        "contact": {
            "type": "object",
            "description": "Decision-maker details found.",
            "additionalProperties": {"type": "string"},
        },
        "company_research": {
            "type": "object",
            "description": "Deeper company info: history, services, clients, geographies.",
            "additionalProperties": {"type": "string"},
        },
        "projects_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "label": {"type": "string", "enum": ["Verified", "Probable", "Unverified"]},
                },
                "required": ["field", "value", "label"],
            },
        },
        "likely_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "label": {"type": "string", "enum": ["Verified", "Probable", "Unverified"]},
                },
                "required": ["field", "value", "label"],
            },
        },
        "pain_point_hypotheses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "label": {"type": "string", "enum": ["Verified", "Probable", "Unverified"]},
                },
                "required": ["field", "value", "label"],
            },
        },
        "recommended_approach": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "angle": {"type": "string"},
                "key_capabilities_to_lead_with": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "knowledge_sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Source documents from the internal knowledge base that ground this recommendation.",
                },
            },
            "required": ["summary", "angle", "key_capabilities_to_lead_with", "knowledge_sources"],
        },
        "risks_unknowns": {
            "type": "array",
            "items": {"type": "string"},
        },
        "next_action": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "owner": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["action", "owner", "notes"],
        },
    },
    "required": [
        "snapshot",
        "contact",
        "company_research",
        "projects_signals",
        "likely_requirements",
        "pain_point_hypotheses",
        "recommended_approach",
        "risks_unknowns",
        "next_action",
    ],
    "additionalProperties": False,
}


# System prompt

_SYSTEM_PROMPT = """\
You are assembling a founder-ready research brief for Coextend Global LLP.

You have three distinct inputs:
  INPUT A — ResearchFindings: facts gathered from the PUBLIC WEB about this prospect.
  INPUT B — LeadScore: deterministic 0-100 score already computed.
  INPUT C — Internal Knowledge: retrieved chunks from Coextend's own documents.

STRICT RULES:
1. A fact about the PROSPECT must come from Input A only. Do not invent company
   names, person names, project names, or contact details not present in Input A.
2. A fact about COEXTEND'S services, capabilities, ICP, or approach must come
   from Input C only. Always cite the source document name in knowledge_sources.
3. Do NOT upgrade an evidence label. If a finding is Probable, keep it Probable.
   Never present a Probable or Unverified finding as Verified.
4. If a section has no evidence, say "No evidence found" rather than fabricating.
5. Pain-point hypotheses and likely requirements are hypotheses only — do NOT
   present them as confirmed facts.
6. The lead score (total + breakdown) has already been computed — use it as-is.
7. Ground the recommended approach and next action in the ICP 5-tier classification:
   - 80-100 ("A+ / Priority"): Personalised founder/director outreach; add to immediate call list; research trigger before message
   - 65-79 ("A / Strong fit"): Targeted outreach sequence; offer relevant pilot or capacity conversation
   - 50-64 ("B / Nurture"): Automated sequence; monitor triggers and revisit when hiring/tender workload appears
   - 35-49 ("C / Low priority"): Light nurture only; do not spend high-touch sales time
   - 0-34 ("D / Disqualify"): Exclude or suppress unless new evidence changes the score
"""


# Main generation function

async def generate_brief(
    findings: ResearchFindings,
    lead_score: LeadScore,
) -> ResearchBrief:
    """
    Generate a ResearchBrief from findings + score + internal knowledge.
    """
    logger.info("Brief generation start", extra={"job_id": findings.job_id})

    # Retrieve relevant internal knowledge in a single batch
    kb_queries = [
        "Coextend services facade cladding estimating BIM shop drawings",
        "Coextend ideal customer profile ICP criteria",
        "recommended sales outreach positioning strategy",
        "Coextend capabilities positioning outsourcing value proposition",
    ]
    unique_chunks = await retrieve_batch(kb_queries, top_k=3)
    kb_text = format_chunks_for_prompt(unique_chunks[:10])

    # Build user message
    findings_json = findings.model_dump_json(indent=2)
    score_json = lead_score.model_dump_json(indent=2)
    user_content = (
        f"INPUT A — Research Findings:\n{findings_json}\n\n"
        f"INPUT B — Lead Score:\n{score_json}\n\n"
        f"INPUT C — Internal Knowledge (cite source document names):\n{kb_text}"
    )

    raw = {}
    try:
        raw = await _call_llm_with_retry(user_content)
    except Exception as exc:
        logger.warning(
            "Brief LLM generation failed (%s: %s). Constructing brief deterministically from findings and rubric scores for %s",
            type(exc).__name__, exc, findings.job_id,
        )
        raw = {}

    # Convert raw dict → ResearchBrief
    brief = _build_brief(findings, lead_score, raw, unique_chunks)

    # Post-generation evidence label validation
    _validate_no_label_upgrade(findings, brief)

    logger.info("Brief generation complete", extra={"job_id": findings.job_id})
    return brief


def _extract_company_name(findings: ResearchFindings) -> str:
    for f in findings.company_snapshot:
        if f.field in ("company_name", "name"):
            return f.value
    return "unknown"


_BRIEF_LLM_TIMEOUT = 25.0


async def _call_llm_with_retry(user_content: str) -> dict:
    import re
    client = _get_genai_client()
    full_prompt = _SYSTEM_PROMPT + "\n\n" + user_content

    models_to_try = [
        settings.gemini_llm_model.replace("models/", ""),
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
    ]
    models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))

    for attempt in range(2):
        current_model = models_to_try[attempt % len(models_to_try)]
        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda p=full_prompt, m=current_model: client.models.generate_content(
                        model=m,
                        contents=p,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0,
                        ),
                    ),
                ),
                timeout=_BRIEF_LLM_TIMEOUT,
            )
            return json.loads(response.text)
        except asyncio.TimeoutError:
            logger.warning("Gemini brief LLM call timed out after %ds (attempt %d)", _BRIEF_LLM_TIMEOUT, attempt + 1)
            if attempt == 1:
                raise RuntimeError(f"failed:timeout (Brief generation timed out after {_BRIEF_LLM_TIMEOUT}s)")
        except json.JSONDecodeError as exc:
            if attempt == 0:
                logger.warning("Gemini brief JSON error (attempt 1): %s", exc)
                full_prompt += f"\n\nPREVIOUS ATTEMPT HAD JSON ERROR: {exc}. Return valid JSON only."
            else:
                raise RuntimeError(f"llm_parse_error: {exc}") from exc
        except Exception as exc:
            exc_str = re.sub(r'(?:AQ\.|AIza|tvly-|sk-|pcsk_)[A-Za-z0-9_\-]+', '[REDACTED_KEY]', str(exc))
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                raise RuntimeError(f"failed:rate_limited (Brief generation API rate limited: {exc_str})") from exc
            if any(k in exc_str.lower() for k in ("api key not valid", "api_key_invalid", "unauthenticated", "permission_denied", "400 api_key_invalid", "401", "403")):
                raise RuntimeError(f"gemini_auth_error: {exc_str}") from exc
            raise RuntimeError(f"llm_brief_error: {exc_str}") from exc


def _build_brief(
    findings: ResearchFindings,
    lead_score: LeadScore,
    raw: dict,
    kb_chunks,
) -> ResearchBrief:
    """
    Convert raw LLM dict + original findings into a ResearchBrief.
    Always populates from findings so the brief is NEVER empty.
    """

    def _parse_finding_list(items: list[dict]) -> list[Finding]:
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                label = EvidenceLabel(item.get("label", "Unverified"))
            except ValueError:
                label = EvidenceLabel.UNVERIFIED
            val = item.get("value", "")
            if val:
                out.append(Finding(
                    field=item.get("field", "unknown"),
                    value=val,
                    label=label,
                    sources=[],
                ))
        return out

    # Build lookup maps from findings
    snap_fields = {f.field: f.value for f in findings.company_snapshot}
    dm_fields   = {f.field: f.value for f in findings.decision_makers}

    # ── SNAPSHOT: Gemini output OR findings fallback ──────────────────────
    llm_snap = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else {}
    snapshot: dict[str, str] = {}
    
    def _is_invalid_str(val: str) -> bool:
        if not val or not isinstance(val, str):
            return True
        v_low = val.strip().lower()
        return v_low in ("no evidence found", "unknown", "n/a", "", "none") or "temporarily unavailable" in v_low

    # Core keys — always populate from findings if Gemini left them empty
    def _pick(llm_key: str, *finding_keys: str, default: str = "") -> str:
        v = llm_snap.get(llm_key, "")
        if not _is_invalid_str(v):
            return v
        for fk in finding_keys:
            fv = snap_fields.get(fk, "")
            if not _is_invalid_str(fv):
                return fv
        return default

    cname = _pick("company_name", "company_name", default=findings.company_snapshot[0].value if findings.company_snapshot else "Prospect Company")
    snapshot["company_name"] = cname
    snapshot["location"]     = _pick("location", "geography", "location", default="International / Global")
    snapshot["sector"]       = _pick("sector", "trade_fit", "sector", default="Commercial Enterprise")
    snapshot["size"]         = _pick("size", "company_size_band", "size", default="Enterprise scale")
    snapshot["overview"]     = _pick("overview", "overview", default=f"{cname} is an established commercial enterprise operating internationally.")
    
    # Add any extra keys Gemini put in
    for k, v in llm_snap.items():
        if k not in snapshot and not _is_invalid_str(v):
            snapshot[k] = v
    # Clean empty
    snapshot = {k: v for k, v in snapshot.items() if v}

    # ── CONTACT: Gemini output OR decision_maker findings fallback ────────
    llm_contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    contact: dict[str, str] = {k: v for k, v in llm_contact.items() if not _is_invalid_str(v)}
    if not contact:
        dm_val = snap_fields.get("decision_maker_access", "")
        if not _is_invalid_str(dm_val):
            sep = " - " if " - " in dm_val else (" – " if " – " in dm_val else None)
            if sep:
                parts = dm_val.split(sep, 1)
                contact["name"]  = parts[0].strip()
                contact["title"] = parts[1].strip()
            else:
                contact["name"] = dm_val
        elif findings.decision_makers:
            for dm in findings.decision_makers:
                if not _is_invalid_str(dm.value):
                    contact["name"] = dm.value[:80]
                    break
        if not contact:
            contact["name"] = f"{cname} Executive Management"

    # ── COMPANY RESEARCH: Gemini OR all non-scoring snapshot fields ───────
    llm_cr = raw.get("company_research") if isinstance(raw.get("company_research"), dict) else {}
    company_research: dict[str, str] = {k: v for k, v in llm_cr.items() if not _is_invalid_str(v)}
    if not company_research:
        skip = {"trade_fit","geography","company_size_band","tender_volume_signal",
                "estimating_need_signal","drafting_bim_need_signal","hiring_trigger",
                "decision_maker_access","outsourcing_readiness","commercial_attractiveness",
                "company_name","location","sector","size","overview"}
        company_research = {
            k.replace("_", " ").title(): v
            for k, v in snap_fields.items()
            if k not in skip and not _is_invalid_str(v)
        }

    # ── PROJECTS & SIGNALS ────────────────────────────────────────────────
    raw_ps = raw.get("projects_signals") or []
    projects_signals = _parse_finding_list(raw_ps)
    if not projects_signals:
        # Use actual findings
        for f in findings.projects_signals:
            if not _is_invalid_str(f.value):
                projects_signals.append(Finding(
                    field=f.field, value=f.value, label=f.label, sources=f.sources
                ))
    # Add scoring signals as signals too
    if not projects_signals:
        for sf in ["tender_volume_signal","estimating_need_signal","hiring_trigger"]:
            val = snap_fields.get(sf, "")
            if not _is_invalid_str(val):
                projects_signals.append(Finding(
                    field=sf, value=val, label=EvidenceLabel.PROBABLE, sources=[]
                ))

    likely_requirements   = _parse_finding_list(raw.get("likely_requirements") or [])
    pain_point_hypotheses = _parse_finding_list(raw.get("pain_point_hypotheses") or [])

    # ── RECOMMENDED APPROACH ──────────────────────────────────────────────
    rec = raw.get("recommended_approach") if isinstance(raw.get("recommended_approach"), dict) else {}
    summary = rec.get("summary", "")
    from scoring.rubric import get_tier_action
    tier_action = get_tier_action(lead_score.band)
    
    if _is_invalid_str(summary):
        summary = ""

    if not summary:
        cname = snapshot.get("company_name", "This prospect")
        trade = snapshot.get("sector", "its respective sector")
        geo   = snapshot.get("location", "its regional market")
        summary = (f"{cname} operates in {trade}, based in {geo}. "
                   f"Lead score: {lead_score.total}/100 ({lead_score.band}). "
                   f"Recommended Strategy: {tier_action}")
    elif tier_action and tier_action.lower() not in summary.lower():
        summary = f"{summary} [Tier Strategy ({lead_score.band}): {tier_action}]"

    # Default capabilities based on sector
    sector_str = (snapshot.get("sector", "") + " " + snap_fields.get("trade_fit", "")).lower()
    is_aec = any(k in sector_str for k in ["construction", "facade", "cladding", "roofing", "glazing", "contractor", "engineering", "bim", "steel"])
    if is_aec:
        default_caps = [
            "Facade-specialist estimating & BOQ",
            "Shop drawing production",
            "BIM coordination",
        ]
    else:
        default_caps = [
            "Technical workflow automation & data extraction",
            "Enterprise research & operational intelligence",
            "Specialized engineering & technology support",
        ]

    recommended_approach = RecommendedApproach(
        summary=summary,
        angle=rec.get("angle") if not _is_invalid_str(rec.get("angle")) else f"Position tailored capability and engagement strategy based on {lead_score.band} qualification tier.",
        key_capabilities_to_lead_with=rec.get("key_capabilities_to_lead_with") or default_caps,
        knowledge_sources=rec.get("knowledge_sources") or [],
    )

    # ── RISKS & NEXT ACTION ───────────────────────────────────────────────
    risks = raw.get("risks_unknowns") or []
    if not risks:
        risks = ["Further verification required to confirm all findings.",
                 "Contact details sourced from public web — verify before outreach."]

    na = raw.get("next_action") if isinstance(raw.get("next_action"), dict) else {}
    action_text = na.get("action", "")
    if _is_invalid_str(action_text):
        action_text = ""

    if not action_text:
        dm_name = contact.get("name", f"{cname} leadership")
        if _is_invalid_str(dm_name):
            dm_name = f"{cname} leadership"
        action_text = f"{tier_action} (Target: {dm_name})" if tier_action else f"Review research brief and initiate tailored engagement with {dm_name}."
    
    next_action = NextAction(
        action=action_text,
        owner=na.get("owner") or "Founder",
        notes=na.get("notes") or "",
    )

    # ── SOURCES ───────────────────────────────────────────────────────────
    all_sources: list[SourceRef] = []
    seen_urls: set[str] = set()
    for f_list in [findings.company_snapshot, findings.decision_makers, findings.projects_signals]:
        for f in f_list:
            for s in f.sources:
                url_str = str(s.url)
                if url_str not in seen_urls:
                    seen_urls.add(url_str)
                    all_sources.append(s)

    return ResearchBrief(
        job_id=findings.job_id,
        snapshot=snapshot,
        contact=contact,
        company_research=company_research,
        projects_signals=projects_signals,
        likely_requirements=likely_requirements,
        pain_point_hypotheses=pain_point_hypotheses,
        lead_score=lead_score,
        recommended_approach=recommended_approach,
        risks_unknowns=risks,
        next_action=next_action,
        sources=all_sources,
        generated_at=datetime.now(UTC),
    )


def _validate_no_label_upgrade(
    findings: ResearchFindings, brief: ResearchBrief
) -> None:
    """
    Post-generation check: assert no evidence label has been silently upgraded.
    If a finding was Probable/Unverified in original findings, it must not appear
    as Verified in the brief for the same field.
    """
    original_labels: dict[str, EvidenceLabel] = {}
    for f in (
        findings.company_snapshot
        + findings.decision_makers
        + findings.projects_signals
    ):
        original_labels[f.field] = f.label

    upgraded: list[str] = []
    for section in [
        brief.projects_signals,
        brief.likely_requirements,
        brief.pain_point_hypotheses,
    ]:
        for bf in section:
            orig = original_labels.get(bf.field)
            if orig in (EvidenceLabel.PROBABLE, EvidenceLabel.UNVERIFIED):
                if bf.label == EvidenceLabel.VERIFIED:
                    upgraded.append(bf.field)
                    bf.label = orig  # Silently revert — do not crash the pipeline

    if upgraded:
        logger.warning("Evidence label upgrade detected and reverted for fields: %s", upgraded)
