"""
Task 8 — CRM adapter tests.
Tests duplicate detection and export structure.
"""
import json
import pytest
from datetime import UTC, datetime
from pathlib import Path

from api.crm_adapter import MockHubSpotAdapter
from api.models import (
    EvidenceLabel,
    Finding,
    LeadScore,
    NextAction,
    RecommendedApproach,
    ResearchBrief,
    ScoreFactor,
)


def make_brief(job_id="test-job-crm", company_name="Harley Facades Ltd", website="https://harleyfacades.com"):
    score = LeadScore(
        rubric_version="v1.0",
        total=65,
        band="A / Strong fit",
        breakdown=[
            ScoreFactor(factor="trade_service_fit", weight=20, points_awarded=15, evidence="facade")
        ],
    )
    return ResearchBrief(
        job_id=job_id,
        snapshot={
            "company_name": company_name,
            "website": website,
            "location": "London, UK",
            "sector": "Facade Contracting",
            "size": "120 employees",
        },
        contact={"first_name": "James", "last_name": "Smith", "title": "Commercial Director"},
        company_research={"overview": "Specialist facade contractor"},
        lead_score=score,
        recommended_approach=RecommendedApproach(
            summary="Lead with estimating services",
            angle="Capacity stretch",
            key_capabilities_to_lead_with=["QS take-off", "BIM"],
            knowledge_sources=["03 - Company Capabilities"],
        ),
        next_action=NextAction(action="Send introduction email", owner="Founder", notes=""),
        generated_at=datetime.now(UTC),
    )


class TestMockHubSpotAdapter:
    @pytest.fixture(autouse=True)
    def setup_exports_dir(self, tmp_path, monkeypatch):
        from config import settings
        monkeypatch.setattr(settings, "exports_path", str(tmp_path / "exports"))
        monkeypatch.setattr(settings, "crm_sample_path", str(tmp_path / "sample_crm.json"))

    @pytest.mark.asyncio
    async def test_export_creates_json_file(self, tmp_path, monkeypatch):
        from config import settings
        exports_dir = tmp_path / "exports"
        monkeypatch.setattr(settings, "exports_path", str(exports_dir))
        monkeypatch.setattr(settings, "crm_sample_path", str(tmp_path / "sample_crm.json"))

        adapter = MockHubSpotAdapter()
        brief = make_brief()
        record = await adapter.export(brief)

        json_path = exports_dir / f"{brief.job_id}_crm.json"
        assert json_path.exists()
        data = json.loads(json_path.read_text())
        assert data["job_id"] == brief.job_id
        assert data["lead_score_total"] == 65

    @pytest.mark.asyncio
    async def test_export_creates_csv_file(self, tmp_path, monkeypatch):
        from config import settings
        exports_dir = tmp_path / "exports"
        monkeypatch.setattr(settings, "exports_path", str(exports_dir))
        monkeypatch.setattr(settings, "crm_sample_path", str(tmp_path / "sample_crm.json"))

        adapter = MockHubSpotAdapter()
        brief = make_brief(job_id="csv-test")
        await adapter.export(brief)

        csv_path = exports_dir / f"{brief.job_id}_crm.csv"
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "job_id" in content
        assert "csv-test" in content

    @pytest.mark.asyncio
    async def test_no_duplicate_when_crm_empty(self, tmp_path, monkeypatch):
        from config import settings
        monkeypatch.setattr(settings, "exports_path", str(tmp_path / "exports"))
        monkeypatch.setattr(settings, "crm_sample_path", str(tmp_path / "sample_crm.json"))

        adapter = MockHubSpotAdapter()
        brief = make_brief()
        record = await adapter.export(brief)
        assert record.possible_duplicate is False

    @pytest.mark.asyncio
    async def test_duplicate_detected_by_name(self, tmp_path, monkeypatch):
        from config import settings
        sample_path = tmp_path / "sample_crm.json"
        sample_path.write_text(json.dumps([
            {"company_name": "Harley Facades Ltd", "website": "https://other.com"}
        ]))
        monkeypatch.setattr(settings, "exports_path", str(tmp_path / "exports"))
        monkeypatch.setattr(settings, "crm_sample_path", str(sample_path))

        adapter = MockHubSpotAdapter()
        brief = make_brief()
        record = await adapter.export(brief)
        assert record.possible_duplicate is True
        # Req 8.5: Confirm no files are written for duplicate
        json_path = (tmp_path / "exports") / f"{brief.job_id}_crm.json"
        csv_path = (tmp_path / "exports") / f"{brief.job_id}_crm.csv"
        assert not json_path.exists()
        assert not csv_path.exists()

    @pytest.mark.asyncio
    async def test_duplicate_detected_by_domain(self, tmp_path, monkeypatch):
        from config import settings
        sample_path = tmp_path / "sample_crm.json"
        sample_path.write_text(json.dumps([
            {"company_name": "Different Name", "website": "https://harleyfacades.com"}
        ]))
        monkeypatch.setattr(settings, "exports_path", str(tmp_path / "exports"))
        monkeypatch.setattr(settings, "crm_sample_path", str(sample_path))

        adapter = MockHubSpotAdapter()
        brief = make_brief()
        record = await adapter.export(brief)
        assert record.possible_duplicate is True
        # Req 8.5: Confirm no files are written for duplicate
        json_path = (tmp_path / "exports") / f"{brief.job_id}_crm.json"
        csv_path = (tmp_path / "exports") / f"{brief.job_id}_crm.csv"
        assert not json_path.exists()
        assert not csv_path.exists()

    @pytest.mark.asyncio
    async def test_duplicate_prevents_file_creation_req_8_5(self, tmp_path, monkeypatch):
        """Req 8.5: System surfaces duplicate instead of creating a new lead/record."""
        from config import settings
        exports_dir = tmp_path / "exports"
        sample_path = tmp_path / "sample_crm.json"
        sample_path.write_text(json.dumps([
            {"company_name": "Apex Facades", "website": "https://apexfacades.com"}
        ]))
        monkeypatch.setattr(settings, "exports_path", str(exports_dir))
        monkeypatch.setattr(settings, "crm_sample_path", str(sample_path))

        adapter = MockHubSpotAdapter()
        dup_brief = make_brief(job_id="dup-lead-001", company_name="Apex Facades", website="https://apexfacades.com")
        record = await adapter.export(dup_brief)

        assert record.possible_duplicate is True
        # Assert neither JSON nor CSV file was written
        assert not (exports_dir / f"{dup_brief.job_id}_crm.json").exists()
        assert not (exports_dir / f"{dup_brief.job_id}_crm.csv").exists()

    @pytest.mark.asyncio
    async def test_export_includes_score_band(self, tmp_path, monkeypatch):
        from config import settings
        monkeypatch.setattr(settings, "exports_path", str(tmp_path / "exports"))
        monkeypatch.setattr(settings, "crm_sample_path", str(tmp_path / "sample_crm.json"))

        adapter = MockHubSpotAdapter()
        brief = make_brief()
        record = await adapter.export(brief)
        assert record.lead_score_band == "A / Strong fit"
        assert record.lead_score_total == 65
