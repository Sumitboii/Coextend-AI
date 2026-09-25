"""
Integration tests for real known companies.
Asserts that the pipeline extracts real structured fields (location, sector, overview)
and does not return generic placeholder text or 'no evidence found' for readily available public data.
"""
import pytest
from api.models import ProspectRequest, ResearchFindings
from engine.researcher import run_research


@pytest.mark.asyncio
async def test_real_company_babel_street():
    """Test research on Babel Street (Software / Risk Intelligence)."""
    req = ProspectRequest(company_name="Babel Street", website="https://www.babelstreet.com")
    findings: ResearchFindings = await run_research("job-real-babelstreet", req)
    
    snap_dict = {f.field: f.value for f in findings.company_snapshot}
    
    # Assert company name
    assert "Babel Street" in snap_dict.get("company_name", "")
    
    # Assert overview is populated and not generic placeholder
    overview = snap_dict.get("overview", "")
    assert overview != ""
    assert "(verified entity record)" not in overview
    assert "no evidence found" not in overview
    
    # Assert geography / location is populated
    geo = snap_dict.get("geography", "")
    loc = snap_dict.get("location", "")
    assert any(k in (geo + " " + loc).lower() for k in ["states", "us", "virginia", "reston", "america", "dc", "washington"])
    
    # Assert sector / trade fit is populated
    trade = snap_dict.get("trade_fit", "")
    sector = snap_dict.get("sector", "")
    assert any(k in (trade + " " + sector).lower() for k in ["risk", "intelligence", "software", "ai", "data", "threat", "platform"])


@pytest.mark.asyncio
async def test_real_company_balfour_beatty():
    """Test research on Balfour Beatty (Infrastructure / Construction)."""
    req = ProspectRequest(company_name="Balfour Beatty", website="https://www.balfourbeatty.com")
    findings: ResearchFindings = await run_research("job-real-balfourbeatty", req)
    
    snap_dict = {f.field: f.value for f in findings.company_snapshot}
    
    assert "Balfour Beatty" in snap_dict.get("company_name", "")
    overview = snap_dict.get("overview", "")
    assert overview != ""
    assert "(verified entity record)" not in overview
    assert "no evidence found" not in overview

    # Geography
    geo = snap_dict.get("geography", "")
    loc = snap_dict.get("location", "")
    assert any(k in (geo + " " + loc).lower() for k in ["uk", "united kingdom", "london", "international", "global", "us"])


@pytest.mark.asyncio
async def test_real_company_eden_facades():
    """Test research on Eden Facades (UK Facade Specialist)."""
    req = ProspectRequest(company_name="Eden Facades Ltd", website="https://edenfacades.co.uk")
    findings: ResearchFindings = await run_research("job-real-edenfacades", req)
    
    snap_dict = {f.field: f.value for f in findings.company_snapshot}
    
    assert "Eden Facades" in snap_dict.get("company_name", "")
    overview = snap_dict.get("overview", "")
    assert overview != ""
    assert "(verified entity record)" not in overview

    # Trade fit / sector
    trade = snap_dict.get("trade_fit", "")
    sector = snap_dict.get("sector", "")
    assert any(k in (trade + " " + sector).lower() for k in ["facade", "cladding", "envelope", "construction", "contractor", "glazing"])
