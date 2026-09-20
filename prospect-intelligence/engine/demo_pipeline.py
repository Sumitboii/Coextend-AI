"""
Demo pipeline - runs without requiring LLM generation.
Uses live web search and homepage scraping to extract dynamic, real facts for any entered company.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

from api.models import (
    EvidenceLabel, Finding, KnowledgeCitation, LeadScore, NextAction,
    OutreachDrafts, RecommendedApproach, ResearchBrief, ResearchFindings, SourceRef,
)
from engine.web_utils import fetch_page, web_search
from scoring.engine import score
from scoring.rubric import get_tier_action

logger = logging.getLogger(__name__)


async def _make_dynamic_findings(job_id: str, company_name: str, website: str) -> ResearchFindings:
    from engine.researcher import _extract_heuristic_fallback, _adapt_gemini_response, _normalise_scoring_fields, _SCORING_FIELDS
    from urllib.parse import urlparse

    if not website.startswith("http"):
        website = "https://" + website

    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]

    # Fetch live homepage and targeted web search snippets
    homepage_task = fetch_page(website, timeout=2.0)
    search_task = web_search(f'"{company_name}" {domain} facade cladding contractor leadership directors', num_results=5)
    
    homepage_text, search_results = await asyncio.gather(homepage_task, search_task, return_exceptions=True)
    
    pages = []
    if isinstance(homepage_text, str) and homepage_text.strip():
        pages.append({"url": website, "text": homepage_text})

    snippets = []
    if isinstance(search_results, list):
        snippets = search_results

    # Run dynamic heuristic extraction from live scraped data
    findings_raw = _extract_heuristic_fallback(company_name, website, pages, snippets)
    findings_raw = _adapt_gemini_response(findings_raw)

    today = date.today()

    def _parse_findings(raw_list: list[dict]) -> list[Finding]:
        out = []
        for item in raw_list:
            sources = [
                SourceRef(url=u, date_reviewed=today)
                for u in item.get("source_urls", [])
                if u
            ]
            try:
                label = EvidenceLabel(item.get("label", "Unverified"))
            except (ValueError, KeyError):
                label = EvidenceLabel.UNVERIFIED
            out.append(
                Finding(
                    field=item.get("field", "unknown"),
                    value=item.get("value", ""),
                    label=label,
                    sources=sources,
                )
            )
        return out

    company_snapshot = _normalise_scoring_fields(_parse_findings(findings_raw.get("company_snapshot", [])))
    decision_makers = _parse_findings(findings_raw.get("decision_makers", []))
    projects_signals = _normalise_scoring_fields(_parse_findings(findings_raw.get("projects_signals", [])))
    notes_missing: list[str] = findings_raw.get("notes_missing", [])

    existing_fields = {f.field for f in company_snapshot}
    for sf in _SCORING_FIELDS:
        if sf not in existing_fields:
            notes_missing.append(f"no evidence found for scoring field: {sf}")
            company_snapshot.append(
                Finding(
                    field=sf,
                    value="no evidence found",
                    label=EvidenceLabel.UNVERIFIED,
                    sources=[],
                )
            )

    return ResearchFindings(
        job_id=job_id,
        company_snapshot=company_snapshot,
        decision_makers=decision_makers,
        projects_signals=projects_signals,
        notes_missing=notes_missing,
    )


def _make_demo_findings(job_id: str, company_name: str, website: str) -> ResearchFindings:
    """Synchronous fallback placeholder for backward compatibility with unit tests."""
    today = date.today()
    if not website.startswith("http"):
        website = "https://" + website

    s = SourceRef(url=website, title=company_name + " - Website", date_reviewed=today)
    snapshot = [
        Finding(field="trade_fit", value="facade cladding roofing contractor", label=EvidenceLabel.VERIFIED, sources=[s]),
        Finding(field="geography", value="UK - national coverage", label=EvidenceLabel.VERIFIED, sources=[s]),
        Finding(field="company_size_band", value="Specialist contractor", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="commercial_attractiveness", value="Commercial contractor with active project portfolio", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="company_name", value=company_name, label=EvidenceLabel.VERIFIED, sources=[s]),
        Finding(field="location", value="UK", label=EvidenceLabel.VERIFIED, sources=[s]),
        Finding(field="sector", value="Facade and Cladding Contracting", label=EvidenceLabel.VERIFIED, sources=[s]),
        Finding(field="overview", value=f"{company_name} is an established facade and cladding contractor delivering projects across the UK.", label=EvidenceLabel.VERIFIED, sources=[s]),
    ]
    decision_makers = [
        Finding(field="decision_maker_access", value="Commercial Director / Leadership Team", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="contact_first_name", value="Team", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="contact_last_name", value="", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="contact_title", value="Commercial Director", label=EvidenceLabel.PROBABLE, sources=[s]),
    ]
    projects_signals = [
        Finding(field="tender_volume_signal", value=f"Commercial tender activity and delivered projects listed for {company_name}", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="estimating_need_signal", value="Standard estimating and quantity takeoff capacity required for bid volumes", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="drafting_bim_need_signal", value="CAD drafting and technical submittal requirements for project specifications", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="hiring_trigger", value="Operational recruitment aligned with active contract delivery", label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="outsourcing_readiness", value="Subcontracting and external partner workflows typical for specialist packages", label=EvidenceLabel.PROBABLE, sources=[s]),
    ]
    return ResearchFindings(
        job_id=job_id,
        company_snapshot=snapshot,
        decision_makers=decision_makers,
        projects_signals=projects_signals,
        notes_missing=[],
    )


def _make_dynamic_brief(findings: ResearchFindings, lead_score: LeadScore, company_name: str) -> ResearchBrief:
    all_sources: list[SourceRef] = []
    seen: set[str] = set()
    for lst in [findings.company_snapshot, findings.decision_makers, findings.projects_signals]:
        for f in lst:
            for src in f.sources:
                u = str(src.url)
                if u not in seen:
                    seen.add(u)
                    all_sources.append(src)

    snap_map = {f.field: f.value for f in findings.company_snapshot}
    dm_map = {f.field: f.value for f in findings.decision_makers}

    trade = snap_map.get("trade_fit", "facade and building envelope contractor")
    loc = snap_map.get("location", snap_map.get("geography", "UK"))
    size = snap_map.get("company_size_band", "Specialist contractor")
    comm = snap_map.get("commercial_attractiveness", "Active commercial projects")
    overview = snap_map.get("overview", f"{company_name} is an established contractor delivering projects across {loc}.")

    contact_name = dm_map.get("decision_maker_access", "Commercial Director")
    first_name = dm_map.get("contact_first_name", "there")
    last_name = dm_map.get("contact_last_name", "")
    title = dm_map.get("contact_title", "Commercial Director")

    tier_action = get_tier_action(lead_score.band)

    return ResearchBrief(
        job_id=findings.job_id,
        snapshot={
            "company_name": company_name,
            "location": loc,
            "sector": snap_map.get("sector", "Commercial Contracting"),
            "size": size,
            "overview": overview,
        },
        contact={
            "name": contact_name,
            "first_name": first_name,
            "last_name": last_name,
            "title": title,
            "linkedin": f"https://linkedin.com/search/results/all/?keywords={company_name.replace(' ', '%20')}",
        },
        company_research={
            "trade": trade,
            "commercial": comm,
            "geography": snap_map.get("geography", loc),
            "services": f"Specialist contracting services in {trade}",
        },
        projects_signals=findings.projects_signals,
        likely_requirements=[
            Finding(field="estimating_support", value="Surge estimating and takeoff capacity to bid current tender pipeline", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="shop_drawing_production", value="Shop drawing production and detailing for active packages", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="bim_coordination", value="BIM coordination and modeling aligned with project specifications", label=EvidenceLabel.PROBABLE, sources=[]),
        ],
        pain_point_hypotheses=[
            Finding(field="capacity_pressure", value="Estimating and commercial capacity stretched during peak tender submissions", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="technical_bandwidth", value="Technical drawing submittal schedules create bottlenecks for project delivery", label=EvidenceLabel.PROBABLE, sources=[]),
        ],
        lead_score=lead_score,
        recommended_approach=RecommendedApproach(
            summary=f"{company_name} operates as a {trade} in {loc}. Lead score: {lead_score.total}/100 ({lead_score.band}). Strategy: {tier_action}",
            angle=f"Surge-capacity technical partnership: back-office take-off and BIM production for {trade} specialists.",
            key_capabilities_to_lead_with=[
                "Facade-specialist quantity take-off and BOQ",
                "Shop drawing production in Revit and AutoCAD",
                "BIM coordination Level 2 delivery",
                "Dedicated UK time-zone resource, zero onboarding lag",
            ],
            knowledge_sources=["05 - Ideal Customer Profile", "04 - Sales Positioning"],
        ),
        risks_unknowns=[
            "Data synthesized via public web and live domain scraper",
            "Contact inferred from web records; direct email verification recommended before high-touch outreach",
        ],
        next_action=NextAction(
            action=f"{tier_action} (Target: {contact_name} at {company_name})",
            owner="Founder",
            notes="Follow up with tailored LinkedIn and email outreach.",
        ),
        sources=all_sources,
        knowledge_citations=[
            KnowledgeCitation(statement="Position as surge-capacity partner", source_document="04 - Sales Positioning", section="Positioning Strategy"),
            KnowledgeCitation(statement="Facade-specialist take-off and BOQ", source_document="05 - Ideal Customer Profile", section="Services Alignment"),
        ],
        generated_at=datetime.now(UTC),
    )


def _make_demo_brief(findings: ResearchFindings, lead_score: LeadScore, company_name: str) -> ResearchBrief:
    """Wrapper for backward compatibility."""
    return _make_dynamic_brief(findings, lead_score, company_name)


def _make_dynamic_outreach(brief: ResearchBrief, company_name: str) -> OutreachDrafts:
    first = brief.contact.get("first_name", "there")
    trade = brief.company_research.get("trade", "specialist contracting")
    email_body = (
        f"Hi {first},\n\n"
        f"I came across {company_name} and your recent work in {trade}.\n\n"
        "When tender pipelines and drawing submittals hit peak volume, contractors often find internal estimating and CAD bandwidth stretched.\n\n"
        "At Coextend, we provide dedicated facade & technical estimating and BIM production support — UK time-zone, specialized in construction packages, with zero onboarding lag.\n\n"
        "Would an introductory 15-minute call this week make sense to discuss your upcoming project pipeline?\n\n"
        "Best regards,\nCoextend Global LLP"
    )
    linkedin_msg = (
        f"Hi {first} — saw {company_name}'s work in {trade}. "
        "We provide dedicated take-off and BIM drawing support to relieve pipeline bottlenecks. "
        "Open to a brief chat?"
    )[:300]

    return OutreachDrafts(
        job_id=brief.job_id,
        email_subject=f"Technical estimating & drawing support for {company_name} - Coextend",
        email_body=email_body,
        linkedin_message=linkedin_msg,
        status="draft",
        generated_at=datetime.now(UTC),
        review_note="draft - requires human review before use",
    )


def _make_demo_outreach(brief: ResearchBrief, company_name: str) -> OutreachDrafts:
    """Wrapper for backward compatibility."""
    return _make_dynamic_outreach(brief, company_name)


async def run_demo_pipeline(
    job_id: str,
    company_name: str,
    website: str,
    update_status_fn,
    save_json_fn,
) -> None:
    from api.models import JobStatus
    try:
        await update_status_fn(job_id, JobStatus.RESEARCHING.value)
        logger.info("RESEARCH (dynamic scraper): researching %s (%s)", company_name, website)
        findings = await _make_dynamic_findings(job_id, company_name, website)
        await save_json_fn(job_id, "findings_json", findings.model_dump(mode="json"))

        await update_status_fn(job_id, JobStatus.SCORING.value)
        lead_score = score(findings)
        await save_json_fn(job_id, "score_json", lead_score.model_dump(mode="json"))

        await update_status_fn(job_id, JobStatus.DRAFTING.value)
        logger.info("DRAFTING: generating dynamic brief for %s", company_name)
        brief = _make_dynamic_brief(findings, lead_score, company_name)
        await save_json_fn(job_id, "brief_json", brief.model_dump(mode="json"))

        from api.crm_adapter import MockHubSpotAdapter
        crm = await MockHubSpotAdapter().export(brief)
        await save_json_fn(job_id, "crm_export_json", crm.model_dump(mode="json"))

        outreach = _make_dynamic_outreach(brief, company_name)
        await save_json_fn(job_id, "outreach_json", outreach.model_dump(mode="json"))

        await update_status_fn(job_id, JobStatus.COMPLETE.value)
        logger.info("PIPELINE COMPLETE for %s", company_name)

    except Exception as exc:
        import traceback
        logger.error("Dynamic pipeline error: %s", traceback.format_exc())
        from api.models import JobStatus
        await update_status_fn(job_id, JobStatus.FAILED.value, str(exc))

