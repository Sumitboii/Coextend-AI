"""
Automated tests for API key authentication (api/auth.py).
Tests:
- No X-API-Key header -> 401 Unauthorized
- Wrong X-API-Key header -> 403 Forbidden
- Correct X-API-Key header -> 200/202 Success
- Open/Development mode when settings.api_key is empty
"""
import pytest
from httpx import ASGITransport, AsyncClient

from config import settings
from main import app


@pytest.fixture
def configure_api_key():
    original_key = settings.api_key
    settings.api_key = "coextend-secret-key-xyz"
    yield "coextend-secret-key-xyz"
    settings.api_key = original_key


@pytest.mark.asyncio
async def test_auth_missing_key_returns_401(configure_api_key):
    """WHEN no API key is passed in headers THEN return 401 Unauthorized."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/prospects",
            json={"company_name": "Auth Test Co", "website": "https://auth-test.com"},
        )
        assert res.status_code == 401
        data = res.json()
        assert "Missing API key" in data.get("detail", "")


@pytest.mark.asyncio
async def test_auth_wrong_key_returns_403(configure_api_key):
    """WHEN an invalid API key is provided THEN return 403 Forbidden."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/prospects",
            headers={"X-API-Key": "invalid-wrong-key"},
            json={"company_name": "Auth Test Co", "website": "https://auth-test.com"},
        )
        assert res.status_code == 403
        data = res.json()
        assert "Invalid API key" in data.get("detail", "")


@pytest.mark.asyncio
async def test_auth_correct_key_succeeds(configure_api_key):
    """WHEN a valid API key is provided THEN request succeeds with 202."""
    valid_key = configure_api_key
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/prospects",
            headers={"X-API-Key": valid_key},
            json={"company_name": "Auth Test Co", "website": "https://auth-test.com"},
        )
        assert res.status_code == 202
        data = res.json()
        assert data.get("status") == "pending"
        assert data.get("company_name") == "Auth Test Co"


@pytest.mark.asyncio
async def test_auth_open_when_api_key_unset():
    """WHEN settings.api_key is empty/unset THEN endpoints allow development access."""
    original_key = settings.api_key
    settings.api_key = ""
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/api/v1/health")
            assert res.status_code == 200
            assert res.json() == {"status": "ok"}
    finally:
        settings.api_key = original_key
