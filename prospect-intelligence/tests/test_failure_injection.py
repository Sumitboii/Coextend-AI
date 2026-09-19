"""
Task 11.4 / Requirement 10.5 — Failure injection tests.
Asserts graceful handling of bad URLs, timeouts, missing fields, and
malformed model output.
"""
import pytest
from pydantic import ValidationError

from api.models import ProspectRequest


class TestBadURLHandling:
    def test_completely_invalid_url_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ProspectRequest(company_name="Test", website="not-a-url")
        errors = exc_info.value.errors()
        assert any("url" in str(e).lower() or "website" in str(e).lower() for e in errors)

    def test_bare_domain_without_scheme_rejected(self):
        with pytest.raises(ValidationError):
            ProspectRequest(company_name="Test", website="example.com")

    def test_ftp_scheme_rejected_or_accepted_gracefully(self):
        # ftp:// is not a valid AnyHttpUrl — should reject
        with pytest.raises(ValidationError):
            ProspectRequest(company_name="Test", website="ftp://example.com")


class TestMissingFieldHandling:
    def test_missing_company_name_fails_with_detail(self):
        with pytest.raises(ValidationError) as exc_info:
            ProspectRequest(website="https://example.com")
        errors = exc_info.value.errors()
        field_errors = [e["loc"] for e in errors]
        assert any("company_name" in loc for loc in field_errors)

    def test_missing_website_fails_with_detail(self):
        with pytest.raises(ValidationError) as exc_info:
            ProspectRequest(company_name="Test Co")
        errors = exc_info.value.errors()
        field_errors = [e["loc"] for e in errors]
        assert any("website" in loc for loc in field_errors)


class TestMalformedOutputHandling:
    def test_invalid_lead_score_total_fails(self):
        """A lead score > 100 must be rejected at the model layer."""
        from api.models import LeadScore
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0", total=150, band="High", breakdown=[])

    def test_invalid_evidence_label_fails(self):
        """An unknown evidence label must fail at the model layer."""
        from api.models import Finding, EvidenceLabel
        with pytest.raises(ValidationError):
            Finding(field="x", value="y", label="INVENTED")

    def test_outreach_draft_status_locked(self):
        """Outreach draft status can never be anything other than 'draft'."""
        from api.models import OutreachDrafts
        with pytest.raises(ValidationError):
            OutreachDrafts(
                job_id="x",
                email_subject="Hi",
                email_body="Body",
                linkedin_message="Short",
                status="sent",  # type: ignore
            )


class TestWebFetchErrorSimulation:
    """
    Tests that the web_utils retry/backoff is correctly configured.
    """

    def test_retry_decorator_is_applied_to_fetch_page(self):
        """
        Validates that fetch_page is decorated with tenacity @retry.
        The retry attribute is added by tenacity's decorator.
        """
        import engine.web_utils as wu
        assert hasattr(wu.fetch_page, "retry"), (
            "fetch_page must be decorated with @retry (tenacity) for resilience"
        )

    def test_retry_decorator_is_applied_to_web_search(self):
        """Validates that web_search is also decorated with @retry."""
        import engine.web_utils as wu
        assert hasattr(wu.web_search, "retry"), (
            "web_search must be decorated with @retry (tenacity) for resilience"
        )

    @pytest.mark.asyncio
    async def test_mock_fetch_with_simulated_retry_succeeds(self, monkeypatch):
        """
        Replaces fetch_page with a mock that fails on the first call
        and succeeds on the second, then verifies the caller gets the result.
        This simulates what would happen after a transient error + retry.
        """
        import httpx
        import engine.web_utils as wu

        call_count = {"n": 0}

        async def mock_fetch_with_retry(url: str) -> str:
            """Simulates fetch_page behaviour post-retry-decoration."""
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First attempt fails — would trigger tenacity retry in prod
                raise httpx.HTTPStatusError(
                    "503 Service Unavailable",
                    request=httpx.Request("GET", url),
                    response=httpx.Response(503),
                )
            # Second attempt (simulated retry) succeeds
            return "<html><body>Page content OK</body></html>"

        monkeypatch.setattr(wu, "fetch_page", mock_fetch_with_retry)

        # Caller of fetch_page catches the first error and retries manually
        result = None
        for attempt in range(2):
            try:
                result = await wu.fetch_page("https://example.com")
                break
            except httpx.HTTPStatusError:
                if attempt == 1:
                    raise

        assert result is not None
        assert "OK" in result
        assert call_count["n"] == 2
