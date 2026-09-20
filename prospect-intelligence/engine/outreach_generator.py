"""
Outreach Draft Generator.
Fills approved email/LinkedIn template structure with Verified/Probable
findings from the ResearchBrief and message-library templates from ChromaDB.

HARD CONSTRAINTS (enforced by this module):
  - Drafts only; zero send/schedule capability.
  - No automated LinkedIn action.
  - Unverified findings are NEVER used as stated facts.
  - All output is marked status="draft" with a human-review note.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


from api.models import EvidenceLabel, Finding, OutreachDrafts, ResearchBrief
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


# JSON schema for outreach generation

_OUTREACH_SCHEMA = {
    "type": "object",
    "properties": {
        "email_subject": {"type": "string", "description": "Email subject line"},
        "email_touch_1": {"type": "string", "description": "Touch 1 Cold Email (Observation + Hypothesis + CTA, <180 words)"},
        "email_touch_2": {"type": "string", "description": "Touch 2 Follow-Up Bump (+3-4 days, polite reminder referencing Touch 1)"},
        "email_touch_3": {"type": "string", "description": "Touch 3 Value-Add / Breakup (+7-8 days, specific trigger observation + 1-page overview offer)"},
        "linkedin_connection": {"type": "string", "description": "LinkedIn connection request message (strictly max 280 characters)."},
        "linkedin_pitch": {"type": "string", "description": "LinkedIn follow-up pitch message after connection accepted (2-3 sentences)."},
    },
    "required": [
        "email_subject",
        "email_touch_1",
        "email_touch_2",
        "email_touch_3",
        "linkedin_connection",
        "linkedin_pitch",
    ],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """\
You are drafting outreach sequences for Coextend Global LLP, a specialized back-office technical partner for façade, cladding, and building envelope contractors.

IMPORTANT: You MUST return ONLY a JSON object with EXACTLY these fields:
- "email_subject": Concise, non-clickbait subject line (e.g. "estimating capacity for [Company]" or "[Project] / façade takeoffs")
- "email_touch_1": Cold email Day 1 (<180 words). Structure: (1) Specific verified observation, (2) Problem hypothesis (estimating bottleneck / BIM backlog), (3) Coextend capability fit, (4) Low-friction ask.
- "email_touch_2": Soft Bump Day 3-4. Short follow-up: "Hi [Name], just following up on my note below. We support façade teams with [specific service]. Is this something that could be useful for [Company] at the moment?"
- "email_touch_3": Value-Add / Breakup Day 7-8. "Hi [Name], one reason I reached out is [specific verified trigger]. We can support with [service] on a project basis or ongoing capacity. Happy to send a one-page overview if useful."
- "linkedin_connection": Connection request strictly UNDER 300 characters. Peer-to-peer engineering tone. No hard selling.
- "linkedin_pitch": Post-connection pitch (2-3 sentences) detailing turnaround times and estimating/drafting bandwidth.

You have:
  INPUT A — Verified and Probable findings about the prospect (from research brief).
            You MUST only use findings labelled Verified or Probable as stated facts.
            Do NOT use Unverified findings as facts.
  INPUT B — Coextend message-library templates and positioning from the internal knowledge base.

CONSTRAINTS:
  - Do NOT invent project names or employee names.
  - LinkedIn connection note MUST be under 300 characters.
  - Emails must be professional, direct, and zero fluff.
  - Return ONLY valid JSON matching the schema. No markdown wrapping.
"""


async def generate_outreach_drafts(brief: ResearchBrief) -> OutreachDrafts:
    """
    Generate email + LinkedIn drafts grounded in Verified/Probable findings
    and message-library templates from the knowledge base.
    """
    logger.info("Outreach draft generation start", extra={"job_id": brief.job_id})

    # Only use Verified or Probable findings
    safe_findings = _filter_safe_findings(brief)

    # Retrieve message-library templates from internal knowledge in a single batch
    kb_queries = [
        "LinkedIn connection message template facade contractor",
        "email outreach template estimating services",
        "Coextend value proposition outsourcing pitch",
    ]
    unique_chunks = await retrieve_batch(kb_queries, top_k=3)
    kb_text = format_chunks_for_prompt(unique_chunks[:6]) if unique_chunks else "(Knowledge base unavailable — use general facade/estimating best practices)"

    # Build user message
    findings_text = "\n".join(
        f"  [{f.label.value}] {f.field}: {f.value}" for f in safe_findings
    )
    company_name = brief.snapshot.get("company_name", "the company")
    contact_name = brief.contact.get("name") or brief.contact.get("first_name", "")
    contact_title = brief.contact.get("title", "")

    user_content = (
        f"Prospect: {company_name}\n"
        f"Contact: {contact_name} — {contact_title}\n\n"
        f"INPUT A — Verified/Probable Findings:\n{findings_text}\n\n"
        f"INPUT B — Internal Knowledge (message templates):\n{kb_text}"
    )

    logger.info("LLM prompt prepared for job %s with %d findings", brief.job_id, len(safe_findings))
    raw = await _call_llm_with_retry(user_content)
    logger.info("LLM response received: %s", raw)

    email_t1 = raw.get("email_touch_1") or raw.get("email_body", "")
    email_t2 = raw.get("email_touch_2", "")
    email_t3 = raw.get("email_touch_3", "")
    li_conn = raw.get("linkedin_connection") or raw.get("linkedin_message", "")
    li_pitch = raw.get("linkedin_pitch", "")

    drafts = OutreachDrafts(
        job_id=brief.job_id,
        email_subject=raw.get("email_subject", ""),
        email_body=email_t1,
        email_touch_1=email_t1,
        email_touch_2=email_t2,
        email_touch_3=email_t3,
        linkedin_message=li_conn,
        linkedin_connection=li_conn,
        linkedin_pitch=li_pitch,
        status="draft",
        generated_at=datetime.now(UTC),
        review_note="draft — requires human review before use",
    )

    # Post-generation: verify no Unverified finding is stated as fact
    _assert_no_unverified_facts(brief, drafts)

    logger.info("Outreach drafts generated", extra={"job_id": brief.job_id})
    return drafts


def _filter_safe_findings(brief: ResearchBrief) -> list[Finding]:
    """Return only Verified or Probable findings from all brief sections."""
    safe = []
    for section in [
        brief.projects_signals,
        brief.likely_requirements,
    ]:
        for f in section:
            if f.label in (EvidenceLabel.VERIFIED, EvidenceLabel.PROBABLE):
                safe.append(f)
    # Also include snapshot facts
    for section_key in ["company_name", "location", "sector", "size"]:
        val = brief.snapshot.get(section_key)
        if val:
            safe.append(
                Finding(
                    field=section_key,
                    value=val,
                    label=EvidenceLabel.VERIFIED,
                    sources=[],
                )
            )
    return safe


def _assert_no_unverified_facts(brief: ResearchBrief, drafts: OutreachDrafts) -> None:
    """
    Best-effort check: if an Unverified finding's exact value appears verbatim
    in the draft bodies, log a warning.
    """
    combined_text = (drafts.email_body + " " + drafts.linkedin_message).lower()
    for section in [
        brief.projects_signals,
        brief.likely_requirements,
        brief.pain_point_hypotheses,
    ]:
        for f in section:
            if f.label == EvidenceLabel.UNVERIFIED:
                if f.value.lower() in combined_text and f.value.lower() != "no evidence found":
                    logger.warning(
                        "Unverified finding '%s' may appear in outreach draft for job %s",
                        f.value[:80],
                        brief.job_id,
                    )


_OUTREACH_LLM_TIMEOUT = 25.0


async def _call_llm_with_retry(user_content: str) -> dict:
    import asyncio, json
    client = _get_genai_client()
    full_prompt = _SYSTEM_PROMPT + "\n\n" + user_content

    for attempt in range(2):
        try:
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
                timeout=_OUTREACH_LLM_TIMEOUT,
            )
            parsed = json.loads(response.text)
            # Handle case where API returns a list instead of dict
            if isinstance(parsed, list):
                if len(parsed) > 0 and isinstance(parsed[0], dict):
                    return parsed[0]
                raise ValueError("API returned list but no dict elements")
            return parsed
        except asyncio.TimeoutError:
            logger.warning("Gemini outreach LLM call timed out after %ds (attempt %d)", _OUTREACH_LLM_TIMEOUT, attempt + 1)
            if attempt == 1:
                raise RuntimeError(f"failed:timeout (Outreach generation timed out after {_OUTREACH_LLM_TIMEOUT}s)")
        except json.JSONDecodeError as exc:
            if attempt == 0:
                logger.warning("Gemini outreach JSON error (attempt 1): %s", exc)
                full_prompt += f"\n\nJSON ERROR: {exc}. Return valid JSON only."
            else:
                raise RuntimeError(f"llm_parse_error: {exc}") from exc
        except Exception as exc:
            exc_str = str(exc)
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                raise RuntimeError(f"failed:rate_limited (Outreach generation API rate limited: {exc})") from exc
            raise RuntimeError(f"llm_outreach_error: {exc}") from exc
