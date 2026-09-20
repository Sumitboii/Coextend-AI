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
    homepage_task = fetch_page(website, timeout=4.0)
    search_task = web_search(f'"{company_name}" {domain} about company overview leadership ceo directors', num_results=5)
    
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

    trade = snap_map.get("trade_fit", snap_map.get("sector", "commercial enterprise"))
    loc = snap_map.get("location", snap_map.get("geography", "Global"))
    size = snap_map.get("size", snap_map.get("company_size_band", "Established enterprise"))
    sector = snap_map.get("sector", snap_map.get("trade_fit", "Commercial Enterprise"))
    comm = snap_map.get("commercial_attractiveness", f"Established commercial operations in {loc}")
    overview = snap_map.get("overview", f"{company_name} is an established {trade} based in {loc}.")

    contact_name = dm_map.get("decision_maker_access", "Leadership Team")
    first_name = dm_map.get("contact_first_name", "there")
    last_name = dm_map.get("contact_last_name", "")
    title = dm_map.get("contact_title", "Director")

    tier_action = get_tier_action(lead_score.band)

    # Detect industry type for dynamic messaging
    trade_lower = trade.lower()
    is_construction = any(k in trade_lower for k in [
        "facade", "cladding", "roofing", "glazing", "structural steel", "fit-out",
        "civil engineering", "groundwork", "contractor", "construction"
    ])
    is_beauty_retail = any(k in trade_lower for k in [
        "cosmetics", "beauty", "personal care", "skincare", "retail", "e-commerce"
    ])
    is_tech = any(k in trade_lower for k in ["software", "saas", "technology", "platform"])
    is_manufacturing = any(k in trade_lower for k in ["manufacturing", "industrial"])

    # Dynamic likely requirements by sector
    if is_construction:
        likely_requirements = [
            Finding(field="estimating_support", value="Surge estimating and takeoff capacity to bid current tender pipeline", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="shop_drawing_production", value="Shop drawing production and detailing for active packages", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="bim_coordination", value="BIM coordination and modeling aligned with project specifications", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        pain_point_hypotheses = [
            Finding(field="capacity_pressure", value="Estimating and commercial capacity stretched during peak tender submissions", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="technical_bandwidth", value="Technical drawing submittal schedules create bottlenecks for project delivery", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        angle = f"Surge-capacity technical partnership: back-office take-off and BIM production for {trade} specialists."
        key_capabilities = [
            "Facade-specialist quantity take-off and BOQ",
            "Shop drawing production in Revit and AutoCAD",
            "BIM coordination Level 2 delivery",
            "Dedicated UK time-zone resource, zero onboarding lag",
        ]
    elif is_beauty_retail:
        likely_requirements = [
            Finding(field="back_office_support", value="Back-office commercial and operations support to scale retail and brand workflows", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="digital_content_production", value="Digital content, product listing, and e-commerce management support", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="data_analytics", value="Sales, inventory, and customer analytics to optimize product range and campaigns", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        pain_point_hypotheses = [
            Finding(field="operational_scale", value=f"Operational bandwidth under pressure as {company_name} scales across markets and product categories", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="digital_transformation", value="Digital workflow integration and e-commerce operations require additional capacity during peak campaigns", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        angle = f"Back-office commercial capacity partnership: operations support tailored for {trade} at scale."
        key_capabilities = [
            "E-commerce operations and product data management",
            "Commercial back-office and administrative support",
            "Sales analytics and reporting workflows",
            "Scalable remote team support with zero onboarding lag",
        ]
    elif is_tech:
        likely_requirements = [
            Finding(field="technical_operations", value="Technical operations and back-office support for scaling SaaS or platform workflows", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="customer_ops", value="Customer operations and support scaling as product adoption grows", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="data_management", value="Data management and reporting support for product and commercial teams", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        pain_point_hypotheses = [
            Finding(field="scale_pressure", value="Rapid growth creates strain on internal operations and support bandwidth", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="ops_efficiency", value="Non-core operations divert engineering and product teams from core development", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        angle = f"Scalable back-office technical operations partner for {company_name}'s growing platform."
        key_capabilities = [
            "Technical operations and admin support at scale",
            "Customer onboarding and support workflows",
            "Data processing and reporting automation",
            "Flexible remote team, fast ramp-up",
        ]
    elif is_manufacturing:
        likely_requirements = [
            Finding(field="technical_documentation", value="Technical documentation, BOMs, and production specification support", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="supply_chain_ops", value="Supply chain coordination and procurement operations support", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="quality_reporting", value="Quality reporting and compliance documentation workflows", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        pain_point_hypotheses = [
            Finding(field="documentation_bottleneck", value="Production documentation and specification workflows create internal bottlenecks", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="ops_capacity", value="Operations team capacity stretched during high-volume production cycles", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        angle = f"Technical back-office capacity support aligned with {company_name}'s manufacturing and production operations."
        key_capabilities = [
            "Technical documentation and BOM production",
            "Supply chain and procurement operations support",
            "Quality and compliance reporting",
            "Scalable remote team, specialist manufacturing domain knowledge",
        ]
    else:
        likely_requirements = [
            Finding(field="back_office_support", value="Back-office operations support to free internal teams for core business activity", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="commercial_ops", value="Commercial operations and reporting support aligned with business growth", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="scalable_capacity", value="Scalable specialist capacity to handle peak workloads without permanent headcount increases", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        pain_point_hypotheses = [
            Finding(field="capacity_pressure", value=f"Internal team capacity stretched as {company_name} grows commercial operations", label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="ops_efficiency", value="Non-core workloads divert senior team attention from strategic priorities", label=EvidenceLabel.PROBABLE, sources=[]),
        ]
        angle = f"Scalable back-office operations partner for {company_name}."
        key_capabilities = [
            "Commercial back-office and operations support",
            "Reporting, analytics, and documentation workflows",
            "Scalable remote team with specialist domain knowledge",
            "Fast ramp-up, zero permanent headcount cost",
        ]

    return ResearchBrief(
        job_id=findings.job_id,
        snapshot={
            "company_name": company_name,
            "location": loc,
            "sector": sector,
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
            "services": f"Services and operations in {trade}",
        },
        projects_signals=findings.projects_signals,
        likely_requirements=likely_requirements,
        pain_point_hypotheses=pain_point_hypotheses,
        lead_score=lead_score,
        recommended_approach=RecommendedApproach(
            summary=f"{company_name} operates as a {trade} in {loc}. Lead score: {lead_score.total}/100 ({lead_score.band}). Strategy: {tier_action}",
            angle=angle,
            key_capabilities_to_lead_with=key_capabilities,
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
            KnowledgeCitation(statement="Position as scalable capacity partner", source_document="04 - Sales Positioning", section="Positioning Strategy"),
            KnowledgeCitation(statement=f"Specialist support for {sector}", source_document="05 - Ideal Customer Profile", section="Services Alignment"),
        ],
        generated_at=datetime.now(UTC),
    )


def _make_demo_brief(findings: ResearchFindings, lead_score: LeadScore, company_name: str) -> ResearchBrief:
    """Wrapper for backward compatibility."""
    return _make_dynamic_brief(findings, lead_score, company_name)


def _make_dynamic_outreach(brief: ResearchBrief, company_name: str) -> OutreachDrafts:
    first = brief.contact.get("first_name", "there")
    trade = brief.company_research.get("trade", "")
    trade_lower = trade.lower()

    is_construction = any(k in trade_lower for k in [
        "facade", "cladding", "roofing", "glazing", "structural steel", "fit-out",
        "civil engineering", "groundwork", "contractor", "construction"
    ])
    is_beauty_retail = any(k in trade_lower for k in [
        "cosmetics", "beauty", "personal care", "skincare", "retail", "e-commerce"
    ])
    is_tech = any(k in trade_lower for k in ["software", "saas", "technology", "platform"])

    if is_construction:
        body_context = (
            f"When tender pipelines and drawing submittals hit peak volume, contractors often find internal estimating and CAD bandwidth stretched.\n\n"
            "At Coextend, we provide dedicated facade & technical estimating and BIM production support — UK time-zone, specialized in construction packages, with zero onboarding lag."
        )
        subject_suffix = "Technical estimating & drawing support"
        linkedin_context = "We provide dedicated take-off and BIM drawing support to relieve pipeline bottlenecks."
    elif is_beauty_retail:
        body_context = (
            f"As {company_name} scales across product categories and channels, back-office operations — from digital content and product data to e-commerce workflows — often become a bottleneck for internal teams.\n\n"
            "At Coextend, we provide scalable back-office commercial operations support — experienced in retail and brand workflows, with zero onboarding lag."
        )
        subject_suffix = "Back-office operations support"
        linkedin_context = "We provide scalable back-office and e-commerce operations support for growing brands."
    elif is_tech:
        body_context = (
            f"As {company_name} grows, internal operations and support teams often struggle to keep pace with product adoption and commercial expansion.\n\n"
            "At Coextend, we provide scalable back-office technical operations support — letting your engineering and product teams stay focused on what matters."
        )
        subject_suffix = "Scalable operations support"
        linkedin_context = "We provide scalable technical operations and support capacity for growing platforms."
    else:
        body_context = (
            f"As {company_name} continues to grow, internal teams often find non-core workloads diverting attention from strategic priorities.\n\n"
            "At Coextend, we provide scalable back-office operations support — commercial, analytical, and administrative capacity on demand, with zero permanent headcount cost."
        )
        subject_suffix = "Back-office operations support"
        linkedin_context = "We provide scalable back-office operations capacity for businesses growing at pace."

    email_body = (
        f"Hi {first},\n\n"
        f"I came across {company_name} and your work in {trade}.\n\n"
        f"{body_context}\n\n"
        "Would an introductory 15-minute call this week make sense to discuss how we might support your team?\n\n"
        "Best regards,\nCoextend Global LLP"
    )
    linkedin_msg = (
        f"Hi {first} — saw {company_name}'s work in {trade}. "
        f"{linkedin_context} "
        "Open to a brief chat?"
    )[:300]

    return OutreachDrafts(
        job_id=brief.job_id,
        email_subject=f"{subject_suffix} for {company_name} - Coextend",
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

