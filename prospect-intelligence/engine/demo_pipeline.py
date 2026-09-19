"""
Demo pipeline - runs entirely without API keys.
Activated when DEMO_MODE=true in .env
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime

from api.models import (
    EvidenceLabel, Finding, KnowledgeCitation, LeadScore, NextAction,
    OutreachDrafts, RecommendedApproach, ResearchBrief, ResearchFindings, SourceRef,
)
from scoring.engine import score

logger = logging.getLogger(__name__)


def _make_demo_findings(job_id: str, company_name: str, website: str) -> ResearchFindings:
    today = date.today()
    if not website.startswith("http"):
        website = "https://" + website

    s  = SourceRef(url=website, title=company_name + " - Website", date_reviewed=today)
    li = SourceRef(url="https://linkedin.com/company/demo", title="LinkedIn Page", date_reviewed=today)
    cf = SourceRef(url="https://contractsfinder.service.gov.uk/demo", title="Contracts Finder", date_reviewed=today)
    j1 = SourceRef(url="https://indeed.co.uk/estimator-demo", title="Indeed - Estimator Vacancy", date_reviewed=today)
    j2 = SourceRef(url="https://indeed.co.uk/bim-demo", title="Indeed - BIM Coordinator Vacancy", date_reviewed=today)

    snapshot = [
        Finding(field="trade_fit",                value="facade cladding roofing contractor",                                   label=EvidenceLabel.VERIFIED,  sources=[s, li]),
        Finding(field="geography",                value="UK - based in Manchester, projects across England",                     label=EvidenceLabel.VERIFIED,  sources=[s]),
        Finding(field="company_size_band",        value="120 employees approx",                                                  label=EvidenceLabel.PROBABLE,  sources=[li]),
        Finding(field="commercial_attractiveness",value="18m turnover, tier-2 main contractor clients, award-winning work",      label=EvidenceLabel.PROBABLE,  sources=[s]),
        Finding(field="company_name",             value=company_name,                                                            label=EvidenceLabel.VERIFIED,  sources=[s]),
        Finding(field="location",                 value="Manchester, UK",                                                        label=EvidenceLabel.VERIFIED,  sources=[s]),
        Finding(field="sector",                   value="Facade and Cladding Contracting",                                       label=EvidenceLabel.VERIFIED,  sources=[s]),
        Finding(field="overview",                 value=company_name + " is a specialist facade and cladding contractor delivering curtain walling, rainscreen cladding, and roofing systems across the UK.", label=EvidenceLabel.VERIFIED, sources=[s]),
    ]

    decision_makers = [
        Finding(field="decision_maker_access", value="James Hargreaves - Commercial Director identified on LinkedIn", label=EvidenceLabel.PROBABLE, sources=[li]),
        Finding(field="contact_first_name",    value="James",               label=EvidenceLabel.PROBABLE, sources=[li]),
        Finding(field="contact_last_name",     value="Hargreaves",          label=EvidenceLabel.PROBABLE, sources=[li]),
        Finding(field="contact_title",         value="Commercial Director",  label=EvidenceLabel.PROBABLE, sources=[li]),
    ]

    projects_signals = [
        Finding(field="tender_volume_signal",     value="Active on multiple frameworks - 3 live tender notices on Contracts Finder",  label=EvidenceLabel.VERIFIED, sources=[cf, s]),
        Finding(field="estimating_need_signal",   value="Senior Estimator vacancy on Indeed - estimating capacity pressure signalled", label=EvidenceLabel.VERIFIED, sources=[j1]),
        Finding(field="drafting_bim_need_signal", value="Shop drawing production and BIM coordination mentioned in project specs",     label=EvidenceLabel.PROBABLE, sources=[s]),
        Finding(field="hiring_trigger",           value="Estimator and BIM Coordinator roles both active on job boards",               label=EvidenceLabel.VERIFIED, sources=[j1, j2]),
        Finding(field="outsourcing_readiness",    value="Previously outsourced take-off work to a QS firm per company blog",           label=EvidenceLabel.PROBABLE, sources=[s]),
    ]

    return ResearchFindings(
        job_id=job_id,
        company_snapshot=snapshot,
        decision_makers=decision_makers,
        projects_signals=projects_signals,
        notes_missing=[],
    )


def _make_demo_brief(findings: ResearchFindings, lead_score: LeadScore, company_name: str) -> ResearchBrief:
    all_sources: list[SourceRef] = []
    seen: set[str] = set()
    for lst in [findings.company_snapshot, findings.decision_makers, findings.projects_signals]:
        for f in lst:
            for src in f.sources:
                u = str(src.url)
                if u not in seen:
                    seen.add(u)
                    all_sources.append(src)

    return ResearchBrief(
        job_id=findings.job_id,
        snapshot={
            "company_name": company_name,
            "location": "Manchester, UK",
            "sector": "Facade and Cladding Contracting",
            "size": "~120 employees",
            "overview": company_name + " is a specialist facade and cladding contractor delivering curtain walling, rainscreen cladding, and roofing systems across the UK.",
        },
        contact={
            "name": "James Hargreaves",
            "first_name": "James",
            "last_name": "Hargreaves",
            "title": "Commercial Director",
            "linkedin": "https://linkedin.com/in/demo",
        },
        company_research={
            "founded": "Est. ~2005",
            "turnover": "~18m GBP (Probable)",
            "clients": "Tier-2 main contractors, NHS frameworks, residential developers",
            "geography": "UK-wide, HQ Manchester",
            "services": "Curtain walling, rainscreen cladding, roof systems, BIM coordination",
        },
        projects_signals=findings.projects_signals,
        likely_requirements=[
            Finding(field="estimating_support",     value="Surge estimating and take-off capacity to bid current tender pipeline",    label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="shop_drawing_production", value="Shop drawing production for 2-3 concurrent facade packages",               label=EvidenceLabel.PROBABLE, sources=[]),
            Finding(field="bim_coordination",        value="BIM Level 2 coordination on active projects - hiring BIM coordinator",     label=EvidenceLabel.PROBABLE, sources=[]),
        ],
        pain_point_hypotheses=[
            Finding(field="capacity_pressure", value="Estimating team stretched - active pipeline and two vacancies suggest capacity cannot absorb current bid volume in-house", label=EvidenceLabel.PROBABLE,   sources=[]),
            Finding(field="bim_shortage",      value="BIM coordinator vacancy suggests internal gap - outsourced BIM and shop drawings could bridge until hire is made",         label=EvidenceLabel.PROBABLE,   sources=[]),
            Finding(field="cost_risk",         value="Missed or late tenders due to estimating bottleneck represents lost revenue",                                               label=EvidenceLabel.UNVERIFIED, sources=[]),
        ],
        lead_score=lead_score,
        recommended_approach=RecommendedApproach(
            summary="Lead with estimating and take-off capacity - the open Estimator vacancy and active tender pipeline are strong signals. Position Coextend as a specialist surge-capacity partner, not a replacement hire. Reference the BIM coordinator vacancy as a second hook.",
            angle="Capacity-relief pitch: You are winning work faster than you can staff for it.",
            key_capabilities_to_lead_with=[
                "Facade-specialist quantity take-off and BOQ",
                "Shop drawing production in Revit and AutoCAD",
                "BIM coordination Level 2 delivery",
                "Dedicated UK time-zone resource, no onboarding lag",
            ],
            knowledge_sources=["05 - Ideal Customer Profile", "04 - Sales Positioning"],
        ),
        risks_unknowns=[
            "Turnover is estimated - not confirmed from public accounts",
            "Contact inferred from LinkedIn - not directly verified",
            "BIM level assumed from project descriptions",
            "No confirmed outsourcing budget identified",
        ],
        next_action=NextAction(
            action="Send email to James Hargreaves referencing the Estimator vacancy and tender activity. Offer a 30-min call.",
            owner="Founder",
            notes="Follow up with LinkedIn connection 3 days after email if no response.",
        ),
        sources=all_sources,
        knowledge_citations=[
            KnowledgeCitation(statement="Position as surge-capacity partner", source_document="04 - Sales Positioning", section="Positioning Strategy"),
            KnowledgeCitation(statement="Facade-specialist take-off and BOQ",  source_document="05 - Ideal Customer Profile", section="Services Alignment"),
        ],
        generated_at=datetime.now(UTC),
    )


def _make_demo_outreach(brief: ResearchBrief, company_name: str) -> OutreachDrafts:
    first = brief.contact.get("first_name", "there")
    email_body = (
        f"Hi {first},\n\n"
        f"I noticed {company_name} has an active Senior Estimator vacancy - and your tender pipeline looks strong right now.\n\n"
        "When internal capacity gets stretched, some of the best facade contractors we work with bring in specialist take-off support to keep bids moving.\n\n"
        "At Coextend, we provide dedicated facade estimating and BOQ production - UK time-zone, facade-specialist, no onboarding lag.\n\n"
        "Would a 20-minute call this week make sense?\n\n"
        "Best regards,\nCoextend Global LLP"
    )
    linkedin_msg = (
        f"Hi {first} - saw {company_name} is hiring an Estimator. "
        "We provide facade-specialist take-off support for contractors with busy pipelines. "
        "Open to a quick call?"
    )[:300]

    return OutreachDrafts(
        job_id=brief.job_id,
        email_subject=f"Facade estimating support for {company_name} - Coextend",
        email_body=email_body,
        linkedin_message=linkedin_msg,
        status="draft",
        generated_at=datetime.now(UTC),
        review_note="draft - requires human review before use",
    )


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
        logger.info("DEMO: researching %s", company_name)
        await asyncio.sleep(2)
        findings = _make_demo_findings(job_id, company_name, website)
        await save_json_fn(job_id, "findings_json", findings.model_dump(mode="json"))

        await update_status_fn(job_id, JobStatus.SCORING.value)
        await asyncio.sleep(1)
        lead_score = score(findings)
        await save_json_fn(job_id, "score_json", lead_score.model_dump(mode="json"))

        await update_status_fn(job_id, JobStatus.DRAFTING.value)
        logger.info("DEMO: generating brief")
        await asyncio.sleep(2)
        brief = _make_demo_brief(findings, lead_score, company_name)
        await save_json_fn(job_id, "brief_json", brief.model_dump(mode="json"))

        from api.crm_adapter import MockHubSpotAdapter
        crm = await MockHubSpotAdapter().export(brief)
        await save_json_fn(job_id, "crm_export_json", crm.model_dump(mode="json"))

        outreach = _make_demo_outreach(brief, company_name)
        await save_json_fn(job_id, "outreach_json", outreach.model_dump(mode="json"))

        await update_status_fn(job_id, JobStatus.COMPLETE.value)
        logger.info("DEMO: complete for %s", company_name)

    except Exception as exc:
        import traceback
        logger.error("DEMO pipeline error: %s", traceback.format_exc())
        from api.models import JobStatus
        await update_status_fn(job_id, JobStatus.FAILED.value, str(exc))
