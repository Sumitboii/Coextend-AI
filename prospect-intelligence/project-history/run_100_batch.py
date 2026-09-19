"""
100 Real-Company Batch Pipeline Runner.
Optimized with Concurrency = 2 (pacing strictly at ~10-12 RPM, below the 15 RPM Gemini free-tier limit).
Skips already-completed companies; persists every result to SQLite immediately.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select

from api.crm_adapter import MockHubSpotAdapter
from api.database import (
    AsyncSessionLocal,
    JobRow,
    LeadScoreRow,
    StorageAdapter,
    init_db,
)
from api.models import JobStatus, ProspectRequest
from engine.brief_generator import generate_brief
from engine.researcher import run_research
from scoring.engine import score

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("batch_run_100.log", encoding="utf-8", mode="a"),
    ],
)
logger = logging.getLogger("batch_runner")

# Semaphore for pacing: 2 concurrent jobs (~10-12 requests/min, well under 15 RPM)
CONCURRENCY_LIMIT = 2
semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)


async def is_already_completed(company_name: str, website: str) -> dict | None:
    """Check if the company is already scored and complete in DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(JobRow, LeadScoreRow)
            .outerjoin(LeadScoreRow, JobRow.job_id == LeadScoreRow.job_id)
            .where(
                (JobRow.company_name == company_name) | (JobRow.website == website),
                JobRow.status == "complete",
            )
            .order_by(JobRow.created_at.desc())
        )
        row = result.first()
        if row and row[0]:
            job, lscore = row
            return {
                "job_id": job.job_id,
                "company_name": job.company_name,
                "website": job.website,
                "status": "complete",
                "score": lscore.total_score if lscore else None,
                "band": lscore.priority_band if lscore else None,
                "elapsed_s": 0.0,
                "error": None,
            }
    return None


async def run_single_prospect_task(
    company_name: str,
    website: str,
    job_index: int,
    total_jobs: int,
) -> dict[str, Any]:
    # Check if already completed in DB
    existing = await is_already_completed(company_name, website)
    if existing and existing["score"] is not None:
        logger.info(
            f"[{job_index}/{total_jobs}] SKIPPED (Already Complete): {company_name} | "
            f"Score: {existing['score']}/100 | Band: {existing['band']}"
        )
        return existing

    async with semaphore:
        import uuid
        job_id = str(uuid.uuid4())
        req = ProspectRequest(company_name=company_name, website=website)
        t0 = time.time()

        async with AsyncSessionLocal() as session:
            await StorageAdapter.create_job(
                session=session,
                job_id=job_id,
                company_name=company_name,
                website=website,
            )
            await StorageAdapter.update_job_status(session, job_id, "researching")

        logger.info(f"[{job_index}/{total_jobs}] START: {company_name} ({website})")

        # Retry loop for rate-limiting 429 backoff
        for attempt in range(3):
            try:
                # 1. External Research
                findings = await run_research(job_id, req)
                
                async with AsyncSessionLocal() as session:
                    await StorageAdapter.save_findings(session, job_id, findings.model_dump(mode="json"))
                    await StorageAdapter.update_job_status(session, job_id, "scoring")

                # 2. Deterministic Scoring
                lead_score = score(findings)

                async with AsyncSessionLocal() as session:
                    await StorageAdapter.save_lead_score(session, job_id, lead_score.model_dump(mode="json"))
                    await StorageAdapter.update_job_status(session, job_id, "drafting")

                # 3. Brief Generation
                brief = await generate_brief(findings, lead_score)

                async with AsyncSessionLocal() as session:
                    await StorageAdapter.save_brief(session, job_id, brief.model_dump(mode="json"))

                # 4. CRM Export
                crm = await MockHubSpotAdapter().export(brief)

                async with AsyncSessionLocal() as session:
                    await StorageAdapter.save_crm_export(session, job_id, crm.model_dump(mode="json"))
                    await StorageAdapter.update_job_status(session, job_id, "complete")

                elapsed = time.time() - t0
                logger.info(
                    f"[{job_index}/{total_jobs}] SUCCESS: {company_name} | "
                    f"Score: {lead_score.total}/100 | Band: {lead_score.band} | Time: {elapsed:.2f}s"
                )
                return {
                    "job_id": job_id,
                    "company_name": company_name,
                    "website": website,
                    "status": "complete",
                    "score": lead_score.total,
                    "band": lead_score.band,
                    "elapsed_s": round(elapsed, 2),
                    "error": None,
                }

            except Exception as exc:
                err_str = str(exc)
                if "429" in err_str or "quota" in err_str.lower() or "resource_exhausted" in err_str.lower():
                    backoff_wait = (attempt + 1) * 8.0
                    logger.warning(
                        f"[{job_index}/{total_jobs}] Rate limit hit for {company_name}. Backoff {backoff_wait:.1f}s (attempt {attempt+1}/3)..."
                    )
                    await asyncio.sleep(backoff_wait)
                    continue
                else:
                    elapsed = time.time() - t0
                    err_msg = f"{type(exc).__name__}: {err_str[:200]}"
                    logger.error(
                        f"[{job_index}/{total_jobs}] FAILED: {company_name} | Reason: {err_msg} | Time: {elapsed:.2f}s"
                    )
                    async with AsyncSessionLocal() as session:
                        await StorageAdapter.update_job_status(session, job_id, "failed", err_msg)
                    return {
                        "job_id": job_id,
                        "company_name": company_name,
                        "website": website,
                        "status": "failed",
                        "score": None,
                        "band": None,
                        "elapsed_s": round(elapsed, 2),
                        "error": err_msg,
                    }

        # If loop exited after 3 retries
        elapsed = time.time() - t0
        err_msg = "RateLimitError: Exceeded max retries on 429 quota"
        logger.error(f"[{job_index}/{total_jobs}] FAILED: {company_name} | Reason: {err_msg}")
        async with AsyncSessionLocal() as session:
            await StorageAdapter.update_job_status(session, job_id, "failed", err_msg)
        return {
            "job_id": job_id,
            "company_name": company_name,
            "website": website,
            "status": "failed",
            "score": None,
            "band": None,
            "elapsed_s": round(elapsed, 2),
            "error": err_msg,
        }


async def run_100_batch():
    print("=" * 70)
    print("COEXTEND AI — 100 REAL-COMPANY BATCH PIPELINE RUN")
    print(f"Concurrency: {CONCURRENCY_LIMIT} Workers | Rate Limits: 15 RPM Paced")
    print("=" * 70)

    await init_db()

    from pathlib import Path
    base_dir = Path(__file__).parent
    data_path = base_dir / "data" / "companies_100.json"
    if not data_path.exists():
        data_path = base_dir / "companies_100.json"
        
    with open(data_path, "r", encoding="utf-8") as f:
        companies = json.load(f)

    total_companies = len(companies)
    print(f"Processing {total_companies} real companies from {data_path}...\n")

    start_time = time.time()

    # Launch tasks with concurrency control
    tasks = [
        run_single_prospect_task(
            company_name=c["company_name"],
            website=c["website"],
            job_index=idx,
            total_jobs=total_companies,
        )
        for idx, c in enumerate(companies, 1)
    ]

    results = await asyncio.gather(*tasks)

    total_elapsed = time.time() - start_time
    total_minutes = total_elapsed / 60.0

    completed = [r for r in results if r["status"] == "complete"]
    failed = [r for r in results if r["status"] == "failed"]
    scores = [r["score"] for r in completed if r["score"] is not None]

    high_band = sum(1 for r in completed if r["band"] == "High")
    med_band = sum(1 for r in completed if r["band"] == "Medium")
    low_band = sum(1 for r in completed if r["band"] == "Low")

    min_score = min(scores) if scores else 0
    max_score = max(scores) if scores else 0
    avg_score = sum(scores) / len(scores) if scores else 0

    print("\n" + "=" * 70)
    print("BATCH EXECUTION COMPLETE — FINAL SUMMARY")
    print("=" * 70)
    print(f"Total Companies Attempted: {total_companies}")
    print(f"Total Succeeded:          {len(completed)} ({len(completed)/total_companies*100:.1f}%)")
    print(f"Total Failed:             {len(failed)} ({len(failed)/total_companies*100:.1f}%)")
    print(f"Total Execution Time:     {total_minutes:.2f} minutes ({total_elapsed:.1f} seconds)")
    print(f"Average Time Per Company: {total_elapsed/total_companies:.2f} seconds")
    print("-" * 70)
    print("SCORE DISTRIBUTION:")
    print(f"  • Min Score:            {min_score}/100")
    print(f"  • Max Score:            {max_score}/100")
    print(f"  • Avg Score:            {avg_score:.2f}/100")
    print("PRIORITY BANDS:")
    print(f"  • High Priority (>=70):  {high_band} ({high_band/total_companies*100:.1f}%)")
    print(f"  • Medium Priority (45-69): {med_band} ({med_band/total_companies*100:.1f}%)")
    print(f"  • Low Priority (<45):   {low_band} ({low_band/total_companies*100:.1f}%)")
    print("-" * 70)

    # Save summary json
    summary_data = {
        "run_timestamp": datetime.now(UTC).isoformat(),
        "total_attempted": total_companies,
        "total_succeeded": len(completed),
        "total_failed": len(failed),
        "total_elapsed_seconds": round(total_elapsed, 2),
        "total_elapsed_minutes": round(total_minutes, 2),
        "avg_seconds_per_company": round(total_elapsed / total_companies, 2),
        "score_statistics": {
            "min_score": min_score,
            "max_score": max_score,
            "avg_score": round(avg_score, 2),
        },
        "priority_band_counts": {
            "High": high_band,
            "Medium": med_band,
            "Low": low_band,
        },
        "results": results,
    }

    summary_file = "batch_100_results_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"Saved full batch results to {summary_file}")


if __name__ == "__main__":
    asyncio.run(run_100_batch())
