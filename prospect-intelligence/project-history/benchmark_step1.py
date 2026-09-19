"""
Benchmark runner for testing pipeline performance and accuracy across 4 fresh companies.
Times every stage and sub-component precisely.
"""
import asyncio
import json
import time
from datetime import datetime
import httpx

from main import app
from api.database import AsyncSessionLocal, init_db, get_job

COMPANIES = [
    {
        "scenario": "Scenario 1: Clear strong-fit façade/construction contractor",
        "company_name": "Eden Facades Ltd",
        "website": "https://www.edenfacades.co.uk",
    },
    {
        "scenario": "Scenario 2: Large non-construction company outside ICP",
        "company_name": "Spotify",
        "website": "https://www.spotify.com",
    },
    {
        "scenario": "Scenario 3: Small/lesser-known company with modest website",
        "company_name": "Concept Facades Ltd",
        "website": "https://www.conceptfacades.co.uk",
    },
    {
        "scenario": "Scenario 4: Minimal/sparse web presence contractor",
        "company_name": "Harts Roofing",
        "website": "https://www.hartsroofing.co.uk",
    },
]

async def run_benchmark():
    await init_db()
    
    # We use httpx.AsyncClient with ASGI transport to test the exact FastAPI endpoints
    transport = httpx.ASGITransport(app=app)
    
    results = []
    
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for idx, comp in enumerate(COMPANIES, 1):
            print(f"\n=======================================================")
            print(f"[{idx}/4] Testing: {comp['company_name']} ({comp['website']})")
            print(f"Scenario: {comp['scenario']}")
            print(f"=======================================================")
            
            t_submit_start = time.perf_counter()
            resp = await client.post("/api/v1/prospects", json={
                "company_name": comp["company_name"],
                "website": comp["website"]
            })
            t_submit_end = time.perf_counter()
            
            if resp.status_code != 202:
                print(f"FAILED to submit: {resp.status_code} {resp.text}")
                continue
                
            job_data = resp.json()
            job_id = job_data["job_id"]
            print(f"Job created: {job_id} (submission took {(t_submit_end - t_submit_start)*1000:.1f}ms)")
            
            # Poll status and track stage timestamps
            stage_history = [("pending", t_submit_start)]
            last_status = "pending"
            
            max_wait = 120.0
            start_poll = time.perf_counter()
            final_job_row = None
            
            while time.perf_counter() - start_poll < max_wait:
                await asyncio.sleep(0.2)
                status_resp = await client.get(f"/api/v1/prospects/{job_id}")
                if status_resp.status_code == 200:
                    st = status_resp.json().get("status")
                    if st != last_status:
                        now_t = time.perf_counter()
                        stage_history.append((st, now_t))
                        print(f"  -> Stage changed to '{st}' at +{now_t - t_submit_start:.2f}s")
                        last_status = st
                    if st in ("complete", "failed"):
                        break
            
            total_wall_clock = time.perf_counter() - t_submit_start
            print(f"Finished in total wall-clock time: {total_wall_clock:.2f}s with status '{last_status}'")
            
            # Fetch brief and score details from DB
            async with AsyncSessionLocal() as session:
                row = await get_job(session, job_id)
                final_job_row = row
            
            brief_data = json.loads(final_job_row.brief_json) if final_job_row and final_job_row.brief_json else {}
            score_data = json.loads(final_job_row.score_json) if final_job_row and final_job_row.score_json else {}
            findings_data = json.loads(final_job_row.findings_json) if final_job_row and final_job_row.findings_json else {}
            
            # Calculate stage durations
            stage_durations = {}
            for i in range(len(stage_history) - 1):
                s_from, t_from = stage_history[i]
                s_to, t_to = stage_history[i+1]
                stage_durations[s_from] = round(t_to - t_from, 3)
            
            results.append({
                "company_name": comp["company_name"],
                "website": comp["website"],
                "scenario": comp["scenario"],
                "job_id": job_id,
                "status": last_status,
                "total_wall_clock_s": round(total_wall_clock, 2),
                "stage_durations": stage_durations,
                "score_total": score_data.get("total"),
                "score_band": score_data.get("band"),
                "score_breakdown": score_data.get("breakdown", []),
                "snapshot": brief_data.get("snapshot", {}),
                "contact": brief_data.get("contact", {}),
                "num_sources": len(brief_data.get("sources", [])),
                "recommended_approach": brief_data.get("recommended_approach", {}),
                "findings_summary": {
                    "num_snapshot": len(findings_data.get("company_snapshot", [])),
                    "num_dms": len(findings_data.get("decision_makers", [])),
                    "num_signals": len(findings_data.get("projects_signals", [])),
                    "notes_missing": findings_data.get("notes_missing", [])
                }
            })
    
    # Save benchmark results
    with open("benchmark_step1_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nBenchmark completed and saved to benchmark_step1_results.json")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
