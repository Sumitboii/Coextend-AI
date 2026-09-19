"""
Unit and integration tests for the Feedback Mechanism (API, Storage, Schema).
"""
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from main import app
from api.database import AsyncSessionLocal, StorageAdapter, get_job, init_db

@pytest.mark.asyncio
async def test_feedback_lifecycle():
    await init_db()
    test_job_id = f"test-fb-{uuid.uuid4()}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create unique test job
        async with AsyncSessionLocal() as session:
            job = await StorageAdapter.create_job(
                session=session,
                job_id=test_job_id,
                company_name="Apex Façades Test",
                website="https://apex-facades-test.com",
            )

        # 2. Submit feedback via POST /api/v1/prospects/{job_id}/feedback
        payload = {
            "score_accuracy": "about_right",
            "brief_quality": "good",
            "outreach_quality": "not_applicable",
            "comment": "Accurate score and crisp brief.",
            "submitted_by": "Test Reviewer",
        }
        res = await client.post(f"/api/v1/prospects/{test_job_id}/feedback", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["job_id"] == test_job_id
        assert data["score_accuracy"] == "about_right"
        assert data["brief_quality"] == "good"
        assert data["comment"] == "Accurate score and crisp brief."
        assert data["submitted_by"] == "Test Reviewer"
        assert "feedback_id" in data

        # 3. Submit second feedback for same job (allow multiple submissions)
        payload2 = {
            "score_accuracy": "too_low",
            "brief_quality": "okay",
            "outreach_quality": "good",
            "comment": "Second review after prospect call.",
            "submitted_by": "Sales Lead",
        }
        res2 = await client.post(f"/api/v1/prospects/{test_job_id}/feedback", json=payload2)
        assert res2.status_code == 201

        # 4. Query job feedbacks via GET /api/v1/prospects/{job_id}/feedback
        get_job_fb = await client.get(f"/api/v1/prospects/{test_job_id}/feedback")
        assert get_job_fb.status_code == 200
        items = get_job_fb.json()
        assert len(items) == 2
        assert items[0]["score_accuracy"] == "too_low"  # latest first

        # 5. Query all feedback via GET /api/v1/feedback
        all_fb = await client.get("/api/v1/feedback")
        assert all_fb.status_code == 200
        all_items = all_fb.json()
        assert any(item["job_id"] == test_job_id for item in all_items)

        # 6. Test 404 for invalid job_id
        res_404 = await client.post("/api/v1/prospects/invalid-uuid-9999/feedback", json=payload)
        assert res_404.status_code == 404

