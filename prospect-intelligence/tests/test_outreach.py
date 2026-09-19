"""
Tests for Multi-Touch Outreach Cadence generation and schema adherence.
Validates 04 - Email Outreach.docx, 05 - Follow Up Messages.docx, and 02/03 LinkedIn Messages.
"""
import pytest
from api.models import (
    EvidenceLabel,
    Finding,
    LeadScore,
    NextAction,
    OutreachDrafts,
    RecommendedApproach,
    ResearchBrief,
    ScoreFactor,
    SourceRef,
)
from engine.outreach_generator import generate_outreach_drafts

@pytest.mark.asyncio
async def test_multi_touch_outreach_generation():
    # Construct realistic research brief for a façade contractor
    brief = ResearchBrief(
        job_id="test-cadence-001",
        snapshot={
            "company_name": "Skyline Envelope Systems Ltd",
            "location": "Manchester, UK",
            "sector": "Façade & Rainscreen Cladding Contractor",
            "size": "45 employees",
        },
        contact={
            "name": "David Sterling",
            "title": "Commercial Director",
        },
        company_research={
            "core_services": "Unitised curtain walling, rainscreen remediation",
        },
        projects_signals=[
            Finding(
                field="recent_tender_win",
                value="Awarded £4.2M residential cladding replacement in Leeds",
                label=EvidenceLabel.VERIFIED,
                sources=[SourceRef(url="https://skyline-envelope.co.uk/news")],
            ),
            Finding(
                field="estimating_capacity",
                value="Currently tendering 6 major commercial packages across North West",
                label=EvidenceLabel.PROBABLE,
                sources=[],
            ),
        ],
        likely_requirements=[
            Finding(
                field="bim_and_takeoff_need",
                value="High volume takeoff and Revit shop drawing bottleneck during peak tender submission",
                label=EvidenceLabel.PROBABLE,
                sources=[],
            ),
        ],
        pain_point_hypotheses=[
            Finding(
                field="estimating_overload",
                value="Estimating team overloaded with multi-tier framework bids",
                label=EvidenceLabel.UNVERIFIED,
                sources=[],
            ),
        ],
        lead_score=LeadScore(
            rubric_version="v1.0",
            total=85,
            band="A+ / Priority",
            breakdown=[
                ScoreFactor(factor="trade_fit", weight=25, points_awarded=25, evidence="Façade specialist"),
            ],
            zero_evidence_factors=[],
        ),
        recommended_approach=RecommendedApproach(
            summary="Lead with estimating & takeoff bandwidth support for current tender load",
            angle="Estimating Capacity Bottleneck",
            key_capabilities_to_lead_with=["Material Takeoffs", "Revit BIM Shop Drawings"],
            knowledge_sources=["01-services", "03-capabilities"],
        ),
        risks_unknowns=["In-house BIM capacity unverified"],
        next_action=NextAction(action="Send Touch 1 email to David Sterling", owner="Sales Lead"),
        sources=[SourceRef(url="https://skyline-envelope.co.uk")],
    )

    drafts: OutreachDrafts = await generate_outreach_drafts(brief)

    # 1. Assert all fields exist and are populated
    assert drafts.job_id == "test-cadence-001"
    assert drafts.status == "draft"
    assert "draft" in drafts.review_note.lower()
    assert len(drafts.email_subject) > 0
    assert len(drafts.email_touch_1) > 0
    assert len(drafts.email_touch_2) > 0
    assert len(drafts.email_touch_3) > 0
    assert len(drafts.linkedin_connection) > 0
    assert len(drafts.linkedin_pitch) > 0

    # 2. Assert LinkedIn connection request length constraint (strictly <= 300 chars)
    assert len(drafts.linkedin_connection) <= 300, (
        f"LinkedIn connection message too long: {len(drafts.linkedin_connection)} chars"
    )

    # 3. Assert backward compatibility aliases
    assert drafts.email_body == drafts.email_touch_1
    assert drafts.linkedin_message == drafts.linkedin_connection
