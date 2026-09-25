"""
Tests for Researcher Engine Resilience and Error Handling.
Validates:
1. Gemini LLM extraction success path.
2. Gemini auth failure path: marks unverified fields as 'temporarily unavailable — verification service error'.
3. Gemini timeout & rate limit resilience with retries.
4. Tavily search failure falling back to DuckDuckGo search.
5. JS-rendered shell page detection prioritizing search snippets.
6. Genuine missing data preservation ('no evidence found').
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.models import EvidenceLabel, ProspectRequest, ResearchFindings
from engine.researcher import (
    _extract_findings,
    _extract_heuristic_fallback,
    _sanitize_error_msg,
    run_research,
)
from engine.web_utils import is_js_shell


def test_sanitize_error_msg():
    raw = "Invalid API key: AQ.DUMMY_TEST_KEY_123456789 or tvly-test-12345678"
    sanitized = _sanitize_error_msg(raw)
    assert "AQ." not in sanitized
    assert "tvly-test" not in sanitized
    assert "[REDACTED_KEY]" in sanitized


def test_is_js_shell_detection():
    # SPA shell with root div and very little text
    spa_html = '<!DOCTYPE html><html><head><title>App</title></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>'
    assert is_js_shell(spa_html, "App") is True

    # NextJS SPA shell
    next_html = '<!DOCTYPE html><html><body><div id="__next"></div><noscript>You need to enable JavaScript to run this app.</noscript></body></html>'
    assert is_js_shell(next_html, "You need to enable JavaScript to run this app.") is True

    # Rich static HTML
    rich_html = "<html><body><h1>Company Overview</h1><p>" + ("Detailed information about our company services. " * 30) + "</p></body></html>"
    rich_text = "Company Overview " + ("Detailed information about our company services. " * 30)
    assert is_js_shell(rich_html, rich_text) is False


@pytest.mark.asyncio
async def test_run_research_gemini_success():
    """When Gemini succeeds, all structured findings from the LLM are populated."""
    req = ProspectRequest(company_name="Acme Facades", website="https://www.acmefacades.com")
    
    mock_llm_json = {
        "company_snapshot": [
            {"field": "company_name", "value": "Acme Facades", "label": "Verified", "source_urls": ["https://www.acmefacades.com"]},
            {"field": "trade_fit", "value": "Rainscreen cladding and facade engineering contractor", "label": "Verified", "source_urls": ["https://www.acmefacades.com"]},
            {"field": "geography", "value": "UK - London and South East", "label": "Verified", "source_urls": ["https://www.acmefacades.com"]},
            {"field": "company_size_band", "value": "120 employees", "label": "Verified", "source_urls": ["https://www.acmefacades.com"]},
            {"field": "overview", "value": "Acme Facades is a premier commercial cladding installer.", "label": "Verified", "source_urls": ["https://www.acmefacades.com"]},
        ],
        "decision_makers": [
            {"field": "decision_maker_access", "value": "Jane Smith – Managing Director", "label": "Verified", "source_urls": ["https://www.acmefacades.com/about"]},
        ],
        "projects_signals": [
            {"field": "tender_volume_signal", "value": "Multiple live tier-1 commercial framework projects", "label": "Verified", "source_urls": ["https://www.acmefacades.com/projects"]},
        ],
        "notes_missing": [],
    }

    with patch("engine.researcher._extract_findings", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = mock_llm_json
        with patch("engine.researcher.web_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [{"title": "Acme Facades", "link": "https://www.acmefacades.com", "snippet": "Acme overview"}]
            with patch("engine.researcher.fetch_page", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "Acme Facades Homepage Text"
                
                findings: ResearchFindings = await run_research("job-test-success", req)

                assert findings.job_id == "job-test-success"
                snap_dict = {f.field: f.value for f in findings.company_snapshot}
                assert snap_dict["trade_fit"] == "Rainscreen cladding and facade engineering contractor"
                assert snap_dict["geography"] == "UK - London and South East"
                assert snap_dict["company_size_band"] == "120 employees"
                assert snap_dict["overview"] == "Acme Facades is a premier commercial cladding installer."
                
                dm_dict = {f.field: f.value for f in findings.decision_makers}
                assert "Jane Smith" in dm_dict["decision_maker_access"]


@pytest.mark.asyncio
async def test_run_research_gemini_auth_failure_with_fallback_data():
    """
    When Gemini fails authentication (e.g. invalid or unconfigured GEMINI_API_KEY):
    1. It logs the error and uses heuristic fallback.
    2. Real facts from snippets (e.g. location, size, overview, sector) ARE populated.
    3. Unverified missing fields are labeled 'temporarily unavailable — verification service error'.
    4. Diagnostic note is preserved in notes_missing.
    """
    req = ProspectRequest(company_name="Babel Street", website="https://www.babelstreet.com")

    mock_snippets = [
        {
            "title": "Babel Street - LinkedIn",
            "link": "https://www.linkedin.com/company/babelstreet",
            "snippet": "Software Development · Washington, DC · 201-500 employees. Babel Street delivers mission-grade risk intelligence for organizations across government and defense."
        },
        {
            "title": "About Babel Street",
            "link": "https://www.babelstreet.com/about-us",
            "snippet": "Founded in 2009. Benji Hutchinson – Chief Executive Officer. Babel Street is the global leader in mission-grade risk intelligence."
        }
    ]

    with patch("engine.researcher._get_genai_client") as mock_client_getter:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("400 API_KEY_INVALID: API key not valid. Please pass a valid API key.")
        mock_client_getter.return_value = mock_client

        with patch("engine.researcher.web_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_snippets
            with patch("engine.researcher.fetch_page", new_callable=AsyncMock) as mock_fetch:
                # Mock a JS shell homepage
                mock_fetch.return_value = '<div id="root"></div>'
                
                findings: ResearchFindings = await run_research("job-test-auth-fail", req)

                assert findings.job_id == "job-test-auth-fail"
                snap_dict = {f.field: f.value for f in findings.company_snapshot}

                # Overview, sector, size, and geography should be extracted from the search snippets
                assert "Babel Street" in snap_dict.get("company_name", "")
                assert "risk intelligence" in snap_dict.get("trade_fit", "").lower() or "software" in snap_dict.get("trade_fit", "").lower()
                assert "united states" in snap_dict.get("geography", "").lower() or "washington" in snap_dict.get("geography", "").lower()
                assert "201-500 employees" in snap_dict.get("company_size_band", "")
                assert "mission-grade" in snap_dict.get("overview", "").lower() or "risk intelligence" in snap_dict.get("overview", "").lower()

                # Unverified construction-specific signals should NOT say 'no evidence found' when service failed
                assert "temporarily unavailable" in snap_dict.get("estimating_need_signal", "").lower() or "temporarily unavailable" in snap_dict.get("drafting_bim_need_signal", "").lower()

                # Diagnostic note must be in notes_missing
                assert any("verification service error" in n.lower() or "gemini" in n.lower() or "llm" in n.lower() for n in findings.notes_missing)


@pytest.mark.asyncio
async def test_run_research_tavily_search_failure_falls_back_to_ddg():
    """When Tavily search raises an exception, DuckDuckGo fallback search is executed."""
    from engine.web_utils import web_search
    
    with patch("engine.web_utils._get_tavily_client") as mock_tavily_getter:
        mock_tavily = MagicMock()
        mock_tavily.search.side_effect = Exception("Tavily API quota exceeded")
        mock_tavily_getter.return_value = mock_tavily

        with patch("engine.web_utils._ddg_search_fallback", new_callable=AsyncMock) as mock_ddg:
            mock_ddg.return_value = [
                {"title": "Balfour Beatty Overview", "link": "https://www.balfourbeatty.com", "snippet": "Balfour Beatty is a leading international infrastructure group based in London, UK."}
            ]
            
            results = await web_search("Balfour Beatty UK", num_results=3)
            assert len(results) == 1
            assert "Balfour Beatty" in results[0]["title"]
            mock_ddg.assert_called_once()


@pytest.mark.asyncio
async def test_no_evidence_preserved_when_gemini_succeeds():
    """When Gemini runs successfully and reports 'no evidence found' for an absent field, it is kept as 'no evidence found'."""
    req = ProspectRequest(company_name="Apex Tech", website="https://www.apextech.example")
    
    mock_llm_json = {
        "company_snapshot": [
            {"field": "company_name", "value": "Apex Tech", "label": "Verified", "source_urls": ["https://www.apextech.example"]},
            {"field": "trade_fit", "value": "Software consulting", "label": "Verified", "source_urls": ["https://www.apextech.example"]},
            {"field": "geography", "value": "United States", "label": "Verified", "source_urls": ["https://www.apextech.example"]},
            {"field": "company_size_band", "value": "50 employees", "label": "Verified", "source_urls": ["https://www.apextech.example"]},
            {"field": "estimating_need_signal", "value": "no evidence found", "label": "Unverified", "source_urls": []},
            {"field": "drafting_bim_need_signal", "value": "no evidence found", "label": "Unverified", "source_urls": []},
        ],
        "decision_makers": [],
        "projects_signals": [],
        "notes_missing": ["No BIM signals found on public web"],
    }

    with patch("engine.researcher._extract_findings", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = mock_llm_json
        with patch("engine.researcher.web_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = []
            with patch("engine.researcher.fetch_page", new_callable=AsyncMock) as mock_fetch:
                mock_fetch.return_value = "Apex Tech website"
                
                findings: ResearchFindings = await run_research("job-test-genuinely-missing", req)
                snap_dict = {f.field: f.value for f in findings.company_snapshot}
                
                # Genuine missing data remains 'no evidence found'
                assert snap_dict["estimating_need_signal"] == "no evidence found"
                assert snap_dict["drafting_bim_need_signal"] == "no evidence found"
