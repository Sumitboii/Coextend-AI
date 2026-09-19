"""
Tests for Proposal Draft Generation (08 - Proposal Templates.docx).
Validates proposal model structure, commercial options, pilot definitions, and API endpoints.
"""
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from api.database import AsyncSessionLocal, StorageAdapter
from api.models import (
    EvidenceLabel,
    Finding,
    LeadScore,
    NextAction,
    ProposalDraft,
    RecommendedApproach,
    ResearchBrief,
    ScoreFactor,
    SourceRef,
)
from engine.proposal_generator import generate_proposal_draft
from main import app


def _create_sample_brief(job_id: str = "test-prop-001") -> ResearchBrief:
    return ResearchBrief(
        job_id=job_id,
        snapshot={
            "company_name": "Apex Cladding & Glazing Ltd",
            "location": "Birmingham, UK",
            "sector": "Rainscreen & Curtain Walling Subcontractor",
            "size": "50-100 staff",
        },
        contact={
            "name": "Sarah Jenkins",
            "title": "Head of Preconstruction",
        },
        company_research={
            "core_services": "Unitised façade engineering and installation",
        },
        projects_signals=[
            Finding(
                field="awarded_schemes",
                value="Secured 3 mid-rise residential developments in West Midlands",
                label=EvidenceLabel.VERIFIED,
                sources=[SourceRef(url="https://apexcladding.example.co.uk")],
            )
        ],
        likely_requirements=[
            Finding(
                field="draughting_capacity",
                value="Spike in 2D GA drafting and fabrication detail drawings needed within 2 weeks",
                label=EvidenceLabel.PROBABLE,
                sources=[],
            )
        ],
        pain_point_hypotheses=[
            Finding(
                field="bid_deadline_pressure",
                value="Preconstruction team working at full capacity across concurrent tenders",
                label=EvidenceLabel.PROBABLE,
                sources=[],
            )
        ],
        lead_score=LeadScore(
            rubric_version="v1.0",
            total=88,
            band="A+ / Priority",
            breakdown=[
                ScoreFactor(factor="trade_fit", weight=25, points_awarded=25, evidence="Façade specialist"),
            ],
            zero_evidence_factors=[],
        ),
        recommended_approach=RecommendedApproach(
            summary="Offer immediate preconstruction draughing and takeoff support on pilot basis",
            angle="Overnight Draughting Bandwidth",
            key_capabilities_to_lead_with=["2D CAD GA Packages", "Material Takeoffs & Schedules"],
            knowledge_sources=["08 - Proposal Templates", "03 - Company Capabilities"],
        ),
        risks_unknowns=[],
        next_action=NextAction(action="Issue proposal to Sarah Jenkins", owner="Sales Director"),
        sources=[SourceRef(url="https://apexcladding.example.co.uk")],
    )


@pytest.mark.asyncio
async def test_proposal_draft_generator_engine():
    brief = _create_sample_brief("test-engine-prop")
    proposal: ProposalDraft = await generate_proposal_draft(brief)

    assert proposal.job_id == "test-engine-prop"
    assert proposal.status == "draft"
    assert len(proposal.proposal_title) > 0
    assert len(proposal.client_requirement) > 0
    assert len(proposal.proposed_scope) >= 1
    assert len(proposal.deliverables) >= 1
    assert len(proposal.turnaround_programme) > 0
    assert isinstance(proposal.commercial_options, list)
    assert len(proposal.commercial_options) >= 1
    assert len(proposal.pilot_option) > 0
    assert len(proposal.assumptions_exclusions) >= 1
    assert "# " in proposal.rendered_markdown
    assert "Coextend" in proposal.rendered_markdown


@pytest.mark.asyncio
async def test_proposal_api_endpoints():
    test_job_id = f"test-prop-api-{uuid.uuid4()}"
    brief = _create_sample_brief(test_job_id)

    from api.database import init_db
    await init_db()

    # Save mock job and brief to database using StorageAdapter
    async with AsyncSessionLocal() as session:
        await StorageAdapter.create_job(
            session=session,
            job_id=test_job_id,
            company_name="Apex Cladding & Glazing Ltd",
            website="https://apexcladding.example.co.uk",
        )
        await StorageAdapter.save_brief(
            session=session,
            job_id=test_job_id,
            brief_dict=brief.model_dump(mode="json"),
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate Proposal via POST
        res_post = await client.post(f"/api/v1/prospects/{test_job_id}/proposal")
        assert res_post.status_code == 200
        data = res_post.json()
        assert data["job_id"] == test_job_id
        assert data["status"] == "draft"
        assert "Apex" in data["proposal_title"] or "Apex" in data.get("client_requirement", "")

        # 2. Retrieve Proposal via GET (JSON)
        res_get_json = await client.get(f"/api/v1/prospects/{test_job_id}/proposal")
        assert res_get_json.status_code == 200
        data_get = res_get_json.json()
        assert data_get["job_id"] == test_job_id
        assert len(data_get["commercial_options"]) >= 1

        # 3. Retrieve Proposal via GET (Markdown format)
        res_get_md = await client.get(f"/api/v1/prospects/{test_job_id}/proposal?format=markdown")
        assert res_get_md.status_code == 200
        assert "text/markdown" in res_get_md.headers.get("content-type", "")
        md_text = res_get_md.text
        assert "# " in md_text
        assert "Commercial Engagement Options" in md_text
        assert "Quality Assurance" in md_text
