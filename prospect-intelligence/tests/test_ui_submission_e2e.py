"""
End-to-end integration test for prospect submission flow:
1. POST /api/v1/prospects -> creates research job.
2. Poll GET /api/v1/prospects/{job_id} until status is complete.
3. GET /api/v1/prospects/{job_id}/brief -> returns populated brief.
4. GET /results/{job_id} -> renders HTML results page.
"""
import asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from api.database import init_db
from config import settings
from main import app


@pytest.mark.asyncio
async def test_ui_submission_e2e_flow():
    await init_db()
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Submit a research job
        payload = {
            "company_name": "Eden Facades Ltd",
            "website": "https://edenfacades.co.uk",
            "known_contact_name": "Paul Davies",
            "known_contact_title": "Commercial Director",
        }
        res_submit = await client.post("/api/v1/prospects", json=payload)
        assert res_submit.status_code == 202
        job_data = res_submit.json()
        job_id = job_data["job_id"]
        assert job_id is not None
        assert job_data["company_name"] == "Eden Facades Ltd"

        # 2. Poll job status until complete or failed (with timeout)
        max_attempts = 45
        final_status = None
        for _ in range(max_attempts):
            await asyncio.sleep(1.0)
            res_status = await client.get(f"/api/v1/prospects/{job_id}")
            assert res_status.status_code == 200
            status_json = res_status.json()
            final_status = status_json["status"]
            if final_status in ("complete", "failed"):
                break

        assert final_status == "complete", f"Expected job to complete, but status was {final_status}"

        # 3. Retrieve completed research brief (JSON)
        res_brief = await client.get(f"/api/v1/prospects/{job_id}/brief")
        assert res_brief.status_code == 200
        brief_data = res_brief.json()
        assert brief_data["job_id"] == job_id
        
        # Verify key fields are populated in the snapshot
        snapshot = brief_data.get("snapshot", {})
        assert snapshot.get("company_name") is not None
        assert snapshot.get("location") not in ("", None)
        assert snapshot.get("sector") not in ("", None)
        
        # Verify lead score exists
        lead_score = brief_data.get("lead_score", {})
        assert "total" in lead_score
        assert "band" in lead_score

        # 4. Verify results HTML UI page renders successfully
        res_ui = await client.get(f"/results/{job_id}")
        assert res_ui.status_code == 200
        assert "text/html" in res_ui.headers.get("content-type", "")
        assert job_id in res_ui.text
