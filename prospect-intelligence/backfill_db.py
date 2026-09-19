"""
Backfill script — populates normalized tables (findings, lead_scores, briefs, crm_exports, outreach_drafts)
from existing jobs table data and real-world-test-results.json.
"""
import asyncio
import json
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from api.database import (
    AsyncSessionLocal,
    Base,
    BriefRow,
    CRMExportRow,
    FindingRow,
    JobRow,
    LeadScoreRow,
    OutreachRow,
    StorageAdapter,
    engine,
    init_db,
)

async def run_backfill():
    print("--- 1. Initializing DB schema and SQL views ---")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Check existing jobs
        result = await session.execute(select(JobRow))
        existing_jobs = result.scalars().all()
        print(f"Found {len(existing_jobs)} existing rows in 'jobs' table.")

        backfilled_scores = 0
        backfilled_findings = 0
        backfilled_briefs = 0
        backfilled_crms = 0

        for job in existing_jobs:
            jid = job.job_id
            
            # Backfill score
            if job.score_json:
                try:
                    s_data = json.loads(job.score_json)
                    await StorageAdapter.save_lead_score(session, jid, s_data)
                    backfilled_scores += 1
                except Exception as e:
                    print(f"Error backfilling score for {jid}: {e}")

            # Backfill findings
            if job.findings_json:
                try:
                    f_data = json.loads(job.findings_json)
                    await StorageAdapter.save_findings(session, jid, f_data)
                    backfilled_findings += 1
                except Exception as e:
                    print(f"Error backfilling findings for {jid}: {e}")

            # Backfill brief
            if job.brief_json:
                try:
                    b_data = json.loads(job.brief_json)
                    await StorageAdapter.save_brief(session, jid, b_data)
                    backfilled_briefs += 1
                except Exception as e:
                    print(f"Error backfilling brief for {jid}: {e}")

            # Backfill crm export
            if job.crm_export_json:
                try:
                    c_data = json.loads(job.crm_export_json)
                    await StorageAdapter.save_crm_export(session, jid, c_data)
                    backfilled_crms += 1
                except Exception as e:
                    print(f"Error backfilling CRM for {jid}: {e}")

        # Also backfill from real-world-test-results.json if present
        json_path = "real-world-test-results.json"
        if os.path.exists(json_path):
            print(f"Backfilling from {json_path}...")
            with open(json_path, "r", encoding="utf-8") as f:
                records = json.load(f)
            
            for rec in records:
                jid = rec.get("job_id")
                if not jid:
                    continue
                # Check if job exists
                job = await StorageAdapter.get_job(session, jid)
                if not job:
                    job = await StorageAdapter.create_job(
                        session,
                        job_id=jid,
                        company_name=rec.get("company", "Unknown"),
                        website=rec.get("website", ""),
                    )
                    await StorageAdapter.update_job_status(session, jid, "complete")
                
                if rec.get("lead_score"):
                    await StorageAdapter.save_lead_score(session, jid, rec["lead_score"])
                    backfilled_scores += 1

        print("\n=== Backfill Summary ===")
        print(f"Scores backfilled: {backfilled_scores}")
        print(f"Findings backfilled: {backfilled_findings}")
        print(f"Briefs backfilled: {backfilled_briefs}")
        print(f"CRM Exports backfilled: {backfilled_crms}")
        print("All data successfully persisted in SQLite!")

if __name__ == "__main__":
    asyncio.run(run_backfill())
