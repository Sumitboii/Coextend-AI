"""
Job service - orchestrates the full research pipeline for one prospect.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from api.database import (
    AsyncSessionLocal, JobRow, create_job, find_recent_job,
    get_job, save_json_field, update_job_status,
)
from api.models import JobRecord, JobStatus, ProspectRequest, ResearchBrief, ResearchFindings
from config import settings

logger = logging.getLogger(__name__)


async def create_research_job(req: ProspectRequest, session: AsyncSession) -> JobRecord:
    from engine.nlp_resolver import resolve_company_entity
    resolved_name, resolved_website, _ = await resolve_company_entity(req.company_name, str(req.website))
    
    existing = await find_recent_job(
        session, resolved_name, resolved_website,
        within_hours=settings.duplicate_cooldown_hours,
    )
    duplicate_warning = existing is not None
    job_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    row = JobRow(
        job_id=job_id,
        status=JobStatus.PENDING.value,
        company_name=resolved_name,
        website=resolved_website,
        known_contact_name=req.known_contact_name,
        known_contact_title=req.known_contact_title,
        created_at=now,
        updated_at=now,
    )
    await create_job(session, row)
    logger.info("Job created: %s for %s (Original: %s)", job_id, resolved_name, req.company_name)
    asyncio.create_task(_run_pipeline(job_id, req))
    return JobRecord(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=now,
        company_name=resolved_name,
        website=resolved_website,
        duplicate_warning=duplicate_warning,
    )


async def get_job_record(job_id: str, session: AsyncSession) -> JobRecord | None:
    row = await get_job(session, job_id)
    return _row_to_record(row) if row else None


def _row_to_record(row: JobRow) -> JobRecord:
    return JobRecord(
        job_id=row.job_id,
        status=JobStatus(row.status),
        created_at=row.created_at,
        company_name=row.company_name,
        website=row.website,
        error_message=row.error_message,
    )


MAX_JOB_TIMEOUT_SECONDS = 120.0


async def _run_pipeline(job_id: str, req: ProspectRequest) -> None:
    async with AsyncSessionLocal() as session:

        async def _update(jid: str, status: str, err: str | None = None) -> None:
            await update_job_status(session, jid, status, err)

        async def _save(jid: str, field: str, data: dict) -> None:
            await save_json_field(session, jid, field, data)

        async def _execute_steps() -> None:
            # DEMO MODE - no API keys required
            if settings.demo_mode:
                logger.info("DEMO MODE active for job %s", job_id)
                from engine.demo_pipeline import run_demo_pipeline
                await run_demo_pipeline(
                    job_id=job_id,
                    company_name=req.company_name,
                    website=str(req.website),
                    update_status_fn=_update,
                    save_json_fn=_save,
                )
                return

            # LIVE MODE - uses Gemini + Tavily API keys
            await _update(job_id, JobStatus.RESEARCHING.value)
            logger.info("Researching %s", job_id)
            from engine.researcher import run_research
            findings = await run_research(job_id, req)
            await _save(job_id, "findings_json", findings.model_dump(mode="json"))

            await _update(job_id, JobStatus.SCORING.value)
            from scoring.engine import score
            lead_score = score(findings)
            await _save(job_id, "score_json", lead_score.model_dump(mode="json"))

            await _update(job_id, JobStatus.DRAFTING.value)
            from engine.brief_generator import generate_brief
            brief = await generate_brief(findings, lead_score)
            await _save(job_id, "brief_json", brief.model_dump(mode="json"))

            from api.crm_adapter import MockHubSpotAdapter
            crm = await MockHubSpotAdapter().export(brief)
            await _save(job_id, "crm_export_json", crm.model_dump(mode="json"))

            await _update(job_id, JobStatus.COMPLETE.value)
            logger.info("Job complete: %s", job_id)

        try:
            await asyncio.wait_for(_execute_steps(), timeout=MAX_JOB_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            reason = f"failed:timeout (Job exceeded maximum allowed duration of {int(MAX_JOB_TIMEOUT_SECONDS)}s)"
            logger.error("Pipeline timed out for %s: %s", job_id, reason)
            await _update(job_id, JobStatus.FAILED.value, reason)
        except Exception as exc:
            exc_str = str(exc)
            # Automatic graceful fallback if API key is invalid or quota exhausted
            if any(k in exc_str.lower() for k in ("api key not valid", "api_key_invalid", "invalid_argument", "quota", "resourceexhausted")):
                logger.warning("Gemini API key error detected (%s). Falling back gracefully to Demo Engine for %s", exc_str, job_id)
                try:
                    from engine.demo_pipeline import run_demo_pipeline
                    await run_demo_pipeline(
                        job_id=job_id,
                        company_name=req.company_name,
                        website=str(req.website),
                        update_status_fn=_update,
                        save_json_fn=_save,
                    )
                    return
                except Exception as fallback_err:
                    logger.exception("Fallback demo pipeline error: %s", fallback_err)
            
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                reason = f"failed:rate_limited (API rate limit exceeded. Please retry after cooldown: {exc_str})"
            elif "timeout" in exc_str.lower():
                reason = f"failed:timeout ({exc_str})"
            else:
                reason = f"{type(exc).__name__}: {exc_str}"
            logger.exception("Pipeline failed for %s: %s", job_id, reason)
            await _update(job_id, JobStatus.FAILED.value, reason)
