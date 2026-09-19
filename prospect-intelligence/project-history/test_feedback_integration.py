"""
Verification script for the Feedback mechanism in Coextend Prospect Intelligence.
Tests API endpoints, database persistence, and Excel export.
"""
import asyncio
import json
import sqlite3
import httpx
from main import app
from export_db_to_excel import export_to_excel, OUTPUT_PATH_1
import openpyxl

async def run_feedback_tests():
    # 1. Connect to SQLite and pick 3 real completed jobs
    conn = sqlite3.connect("data/prospect_intelligence.db")
    cur = conn.cursor()
    cur.execute("SELECT job_id, company_name FROM jobs WHERE status='complete' LIMIT 3;")
    jobs = cur.fetchall()
    conn.close()

    assert len(jobs) >= 3, f"Need at least 3 completed jobs, found {len(jobs)}"
    print(f"Testing with 3 existing jobs: {[j[1] for j in jobs]}")

    job1_id, job1_name = jobs[0]
    job2_id, job2_name = jobs[1]
    job3_id, job3_name = jobs[2]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # -------------------------------------------------------------
        # 2. Test POST /api/v1/prospects/{job_id}/feedback
        # -------------------------------------------------------------
        print("\n--- Testing POST feedback ---")
        
        fb1_data = {
            "score_accuracy": "about_right",
            "brief_quality": "good",
            "outreach_quality": "not_applicable",
            "comment": f"Excellent brief depth for {job1_name}. Score accurately reflects envelope specialization.",
            "submitted_by": "SS (Sales Lead)"
        }
        res1 = await client.post(f"/api/v1/prospects/{job1_id}/feedback", json=fb1_data)
        assert res1.status_code == 201, f"Expected 201, got {res1.status_code}: {res1.text}"
        rec1 = res1.json()
        print(f"Job 1 Feedback Created: ID={rec1['feedback_id']}, Accuracy={rec1['score_accuracy']}, Score={rec1['total_score']}")

        fb2_data = {
            "score_accuracy": "too_low",
            "brief_quality": "okay",
            "outreach_quality": "good",
            "comment": f"Has dedicated rainscreen division; could score slightly higher on envelope specialization.",
            "submitted_by": "JM (Analyst)"
        }
        res2 = await client.post(f"/api/v1/prospects/{job2_id}/feedback", json=fb2_data)
        assert res2.status_code == 201, f"Expected 201, got {res2.status_code}: {res2.text}"
        rec2 = res2.json()
        print(f"Job 2 Feedback Created: ID={rec2['feedback_id']}, Accuracy={rec2['score_accuracy']}, Score={rec2['total_score']}")

        fb3_data = {
            "score_accuracy": "about_right",
            "brief_quality": "good",
            "outreach_quality": "okay",
            "comment": f"Good targeting on cladding remediation and warranty hook.",
            "submitted_by": "AR (Solutions Engineer)"
        }
        res3 = await client.post(f"/api/v1/prospects/{job3_id}/feedback", json=fb3_data)
        assert res3.status_code == 201, f"Expected 201, got {res3.status_code}: {res3.text}"
        rec3 = res3.json()
        print(f"Job 3 Feedback Created: ID={rec3['feedback_id']}, Accuracy={rec3['score_accuracy']}, Score={rec3['total_score']}")

        # Test multiple feedback submissions for the same job (Job 1)
        fb1_second_data = {
            "score_accuracy": "about_right",
            "brief_quality": "good",
            "outreach_quality": "good",
            "comment": "Follow-up review after outreach customization: resonance was high.",
            "submitted_by": "SS (Sales Lead)"
        }
        res1_second = await client.post(f"/api/v1/prospects/{job1_id}/feedback", json=fb1_second_data)
        assert res1_second.status_code == 201
        print(f"Job 1 Second Feedback Created (Multiple submissions verified).")

        # Test 404 on non-existent job
        res_404 = await client.post("/api/v1/prospects/non-existent-uuid-1234/feedback", json=fb1_data)
        assert res_404.status_code == 404, f"Expected 404, got {res_404.status_code}"
        print("Non-existent Job 404 correctly handled.")

        # -------------------------------------------------------------
        # 3. Test GET /api/v1/prospects/{job_id}/feedback
        # -------------------------------------------------------------
        print("\n--- Testing GET job feedback ---")
        get_res1 = await client.get(f"/api/v1/prospects/{job1_id}/feedback")
        assert get_res1.status_code == 200
        job1_feedbacks = get_res1.json()
        assert len(job1_feedbacks) >= 2, f"Expected at least 2 feedbacks for job1, got {len(job1_feedbacks)}"
        print(f"GET /prospects/{job1_id}/feedback returned {len(job1_feedbacks)} records as expected.")

        # -------------------------------------------------------------
        # 4. Test GET /api/v1/feedback
        # -------------------------------------------------------------
        print("\n--- Testing GET all feedback ---")
        all_res = await client.get("/api/v1/feedback")
        assert all_res.status_code == 200
        all_feedbacks = all_res.json()
        assert len(all_feedbacks) >= 4, f"Expected at least 4 feedbacks, got {len(all_feedbacks)}"
        print(f"GET /feedback returned {len(all_feedbacks)} total records.")
        print(f"Sample full record: {json.dumps(all_feedbacks[0], indent=2)}")

    # -------------------------------------------------------------
    # 5. Test Excel Export with Feedback Sheet
    # -------------------------------------------------------------
    print("\n--- Testing Excel Export with User_Feedback sheet ---")
    export_to_excel()

    wb = openpyxl.load_workbook(OUTPUT_PATH_1)
    sheet_names = wb.sheetnames
    print(f"Excel Sheet Names ({len(sheet_names)}): {sheet_names}")
    assert "Feedback" in sheet_names, "Feedback sheet missing from Excel!"

    ws = wb["Feedback"]
    print(f"Feedback Sheet Rows: {ws.max_row}, Columns: {ws.max_column}")
    for row in ws.iter_rows(values_only=True):
        print("  ", row)
    
    assert ws.max_row >= 5, f"Expected at least 5 rows (1 header + 4 data), got {ws.max_row}"
    print("\n[SUCCESS] All Feedback mechanism verification checks passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_feedback_tests())
