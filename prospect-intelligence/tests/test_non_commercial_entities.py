"""
Test suite asserting that non-commercial entities (Universities, Government, Hospitals, Law Firms, Charities)
are never fabricated as commercial façade contractors, and score 0 on Trade Fit in both LLM and Fallback modes.
"""
import pytest
from api.models import EvidenceLabel, Finding, ResearchFindings
from scoring.engine import score
from scoring.rubric import RUBRIC_VERSION
from engine.researcher import _extract_heuristic_fallback


def test_university_entity_fallback_zero_trade_fit():
    """Pune University in fallback mode must be classified as higher education, never cosmetics or facade contractor."""
    company = "savitribai phule pune univercity"
    website = "https://www.unipune.ac.in/"
    pages = [{"url": website, "text": "Savitribai Phule Pune University, one of the premier universities in India. Established under the Poona University Act."}]
    snippets = [{"title": "Pune University", "link": website, "snippet": "Official website of Savitribai Phule Pune University."}]

    raw = _extract_heuristic_fallback(company, website, pages, snippets)
    
    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    sector_item = next(item for item in raw["company_snapshot"] if item["field"] == "sector")
    dm_item = next(item for item in raw["decision_makers"] if item["field"] == "decision_maker_access")

    assert trade_item["value"] == "higher education institution"
    assert sector_item["value"] == "Education & Academic Research"
    assert trade_item["label"] == "Unverified"
    # Never invent a fake generic director contact
    assert dm_item["value"] == "no evidence found"

    # Score should award 0 for trade fit
    findings = ResearchFindings(
        job_id="test-uni",
        company_snapshot=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["company_snapshot"]],
        decision_makers=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["decision_makers"]],
        projects_signals=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["projects_signals"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")
    assert trade_factor.points_awarded == 0
    assert s.band == "D / Disqualify"


def test_government_entity_fallback_zero_trade_fit():
    """UK Government entity must be classified as government body, score 0 on Trade Fit."""
    company = "HM Revenue & Customs"
    website = "https://www.gov.uk/government/organisations/hm-revenue-customs"
    pages = [{"url": website, "text": "HM Revenue & Customs is a non-ministerial department of the UK Government."}]
    snippets = [{"title": "HMRC", "link": website, "snippet": "UK government department responsible for the collection of taxes."}]

    raw = _extract_heuristic_fallback(company, website, pages, snippets)
    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    assert trade_item["value"] == "government body or public entity"

    findings = ResearchFindings(
        job_id="test-gov",
        company_snapshot=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["company_snapshot"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")
    assert trade_factor.points_awarded == 0


def test_healthcare_hospital_entity_fallback_zero_trade_fit():
    """NHS hospital must be classified as healthcare provider, score 0 on Trade Fit."""
    company = "Manchester University NHS Foundation Trust"
    website = "https://mft.nhs.uk/"
    pages = [{"url": website, "text": "Manchester University NHS Foundation Trust provides hospital care and medical services."}]
    snippets = [{"title": "MFT NHS", "link": website, "snippet": "Leading NHS healthcare provider in the North West."}]

    raw = _extract_heuristic_fallback(company, website, pages, snippets)
    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    assert trade_item["value"] == "healthcare provider / medical institution"

    findings = ResearchFindings(
        job_id="test-nhs",
        company_snapshot=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["company_snapshot"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")
    assert trade_factor.points_awarded == 0


def test_law_firm_entity_fallback_zero_trade_fit():
    """Law firm must be classified as legal services practice, score 0 on Trade Fit."""
    company = "Clifford Chance"
    website = "https://www.cliffordchance.com/"
    pages = [{"url": website, "text": "Clifford Chance is a multinational law firm with solicitors and attorneys at law worldwide."}]
    snippets = [{"title": "Clifford Chance", "link": website, "snippet": "Global legal practice and corporate solicitors."}]

    raw = _extract_heuristic_fallback(company, website, pages, snippets)
    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    assert trade_item["value"] == "legal services practice"

    findings = ResearchFindings(
        job_id="test-law",
        company_snapshot=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["company_snapshot"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")
    assert trade_factor.points_awarded == 0


def test_charity_entity_fallback_zero_trade_fit():
    """Non-profit charity must be classified as non-profit organization, score 0 on Trade Fit."""
    company = "British Red Cross"
    website = "https://www.redcross.org.uk/"
    pages = [{"url": website, "text": "The British Red Cross is a registered charity helping people in crisis with humanitarian aid."}]
    snippets = [{"title": "British Red Cross", "link": website, "snippet": "Registered charity and humanitarian non-profit organization."}]

    raw = _extract_heuristic_fallback(company, website, pages, snippets)
    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    assert trade_item["value"] == "non-profit organization"

    findings = ResearchFindings(
        job_id="test-ngo",
        company_snapshot=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["company_snapshot"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")
    assert trade_factor.points_awarded == 0


def test_genuine_facade_contractor_fallback_matches_trade():
    """Genuine facade contractor must be accurately recognized and score 20 on Trade Fit."""
    company = "Harley Facades Ltd"
    website = "https://www.harleyfacades.co.uk/"
    pages = [{"url": website, "text": "Harley Facades Ltd is a specialist facade contractor and architectural glazing contractor based in the UK."}]
    snippets = [{"title": "Harley Facades", "link": website, "snippet": "Leading cladding contractor and rainscreen cladding specialist."}]

    raw = _extract_heuristic_fallback(company, website, pages, snippets)
    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    assert trade_item["value"] == "facade and cladding contractor"

    findings = ResearchFindings(
        job_id="test-facade",
        company_snapshot=[Finding(field=item["field"], value=item["value"], label=EvidenceLabel.UNVERIFIED) for item in raw["company_snapshot"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")
    assert trade_factor.points_awarded == 20
