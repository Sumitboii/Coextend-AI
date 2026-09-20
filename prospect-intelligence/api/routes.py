"""
FastAPI route handlers — thin; all business logic lives in services.
"""
from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_session, get_job, StorageAdapter
from api.job_service import create_research_job, get_job_record
from api.models import (
    CRMExportRecord,
    FeedbackCreate,
    FeedbackRecord,
    JobRecord,
    OutreachDrafts,
    ProposalDraft,
    ProspectRequest,
    ResearchBrief,
)

logger = logging.getLogger(__name__)
router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# Health

@router.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok"}


# Prospect / job lifecycle

@router.post("/prospects", response_model=JobRecord, status_code=202, tags=["prospects"])
async def create_prospect(req: ProspectRequest, session: SessionDep) -> JobRecord:
    """
    Submit a new prospect for research.
    Returns immediately with a job_id; poll GET /prospects/{job_id} for status.
    """
    return await create_research_job(req, session)


@router.get("/prospects", tags=["prospects"])
async def list_prospects(session: SessionDep, limit: int = 50, offset: int = 0) -> list[dict]:
    """List all researched prospects ordered by score descending."""
    try:
        stmt = text(
            "SELECT j.job_id, j.company_name, j.website, s.total_score, s.priority_band, j.status, j.created_at "
            "FROM jobs j "
            "LEFT JOIN lead_scores s ON j.job_id = s.job_id "
            "ORDER BY j.created_at DESC "
            "LIMIT :limit OFFSET :offset"
        )
        result = await session.execute(stmt, {"limit": limit, "offset": offset})
        rows = result.mappings().all()
        return [
            {
                "job_id": str(r["job_id"]),
                "company_name": r["company_name"] or "Unknown",
                "website": r["website"] or "",
                "total_score": r["total_score"] or 0,
                "priority_band": r["priority_band"] or "Unscored",
                "status": r["status"] or "pending",
                "created_at": str(r["created_at"]) if r["created_at"] else None,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.exception("Error listing prospects: %s", exc)
        return []


@router.get("/prospects/{job_id}", response_model=JobRecord, tags=["prospects"])
async def get_prospect_status(job_id: str, session: SessionDep) -> JobRecord:
    """Return current job status and summary."""
    record = await get_job_record(job_id, session)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return record


# Brief

@router.get("/prospects/{job_id}/brief", tags=["prospects"])
async def get_brief(job_id: str, session: SessionDep, format: str = "json"):
    """
    Return the completed research brief.
    ?format=json (default) or ?format=markdown
    """
    row = await get_job(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if not row.brief_json:
        raise HTTPException(
            status_code=409,
            detail=f"Brief not yet available. Job status: {row.status}",
        )
    data = json.loads(row.brief_json)
    if format == "markdown":
        brief = ResearchBrief(**data)
        md = _brief_to_markdown(brief)
        return Response(content=md, media_type="text/markdown")
    return data


# CRM export

@router.get("/prospects/{job_id}/crm-export", tags=["prospects"])
async def get_crm_export(job_id: str, session: SessionDep, format: str = "json"):
    """
    Return the CRM-ready export for a completed job.
    ?format=json (default) or ?format=csv
    """
    row = await get_job(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if not row.crm_export_json:
        raise HTTPException(
            status_code=409,
            detail=f"CRM export not yet available. Job status: {row.status}",
        )
    data = json.loads(row.crm_export_json)
    if format == "csv":
        record = CRMExportRecord(**data)
        csv_content = _crm_to_csv(record)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={job_id}_crm.csv"},
        )
    return data


# Outreach drafts

@router.post("/prospects/{job_id}/outreach", response_model=OutreachDrafts, tags=["prospects"])
async def generate_outreach(job_id: str, session: SessionDep) -> OutreachDrafts:
    """Generate outreach drafts on demand for a completed research job."""
    row = await get_job(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if not row.brief_json:
        raise HTTPException(
            status_code=409,
            detail=f"Brief not yet available for outreach. Job status: {row.status}",
        )
    if row.outreach_json:
        # Already generated — return cached
        return OutreachDrafts(**json.loads(row.outreach_json))

    from api.database import save_json_field
    from engine.outreach_generator import generate_outreach_drafts

    brief_data = json.loads(row.brief_json)
    brief = ResearchBrief(**brief_data)
    drafts: OutreachDrafts = await generate_outreach_drafts(brief)
    await save_json_field(session, job_id, "outreach_json", drafts.model_dump(mode="json"))
    return drafts


# Proposal Drafts (08 - Proposal Templates.docx)

@router.post("/prospects/{job_id}/proposal", response_model=ProposalDraft, tags=["prospects"])
async def generate_proposal(job_id: str, session: SessionDep) -> ProposalDraft:
    """Generate a tailored Scope of Work proposal draft for a prospect."""
    row = await get_job(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if not row.brief_json:
        raise HTTPException(
            status_code=409,
            detail=f"Brief not yet available for proposal generation. Job status: {row.status}",
        )
    if row.proposal_json:
        return ProposalDraft(**json.loads(row.proposal_json))

    from api.database import save_json_field
    from engine.proposal_generator import generate_proposal_draft

    brief_data = json.loads(row.brief_json)
    brief = ResearchBrief(**brief_data)
    proposal: ProposalDraft = await generate_proposal_draft(brief)
    await save_json_field(session, job_id, "proposal_json", proposal.model_dump(mode="json"))
    return proposal


@router.get("/prospects/{job_id}/proposal", tags=["prospects"])
async def get_proposal(job_id: str, session: SessionDep, format: str = "json"):
    """
    Retrieve generated proposal draft.
    ?format=json (default) or ?format=markdown
    """
    row = await get_job(session, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if not row.proposal_json:
        raise HTTPException(
            status_code=409,
            detail=f"Proposal not yet generated for job '{job_id}'. Call POST /prospects/{job_id}/proposal first.",
        )
    data = json.loads(row.proposal_json)
    if format == "markdown":
        return Response(
            content=data.get("rendered_markdown", ""),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename={job_id}_proposal.md"},
        )
    return data



# Knowledge re-ingestion

@router.post("/knowledge/ingest", tags=["knowledge"])
async def ingest_knowledge() -> dict:
    """
    (Re)ingest all Coextend PDFs from the configured knowledge_base_path.
    Safe to call again when a document is updated — no code change required.
    """
    from knowledge.ingestion import ingest_knowledge_base
    result = await ingest_knowledge_base()
    return {"status": "ok", "chunks_indexed": result}


# Feedback

@router.post(
    "/prospects/{job_id}/feedback",
    response_model=FeedbackRecord,
    status_code=201,
    tags=["feedback"],
)
async def submit_feedback(
    job_id: str,
    feedback_in: FeedbackCreate,
    session: SessionDep,
) -> FeedbackRecord:
    """
    Submit user feedback on scoring accuracy, brief quality, and outreach quality.
    Allows multiple submissions per job.
    """
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    row = await StorageAdapter.save_feedback(session, job_id, feedback_in.model_dump())

    # Fetch score info if available
    total_score = None
    priority_band = None
    if job.score_json:
        try:
            score_data = json.loads(job.score_json)
            total_score = score_data.get("total")
            priority_band = score_data.get("band")
        except Exception:
            pass

    return FeedbackRecord(
        feedback_id=row.feedback_id,
        job_id=row.job_id,
        score_accuracy=row.score_accuracy,
        brief_quality=row.brief_quality,
        outreach_quality=row.outreach_quality,
        comment=row.comment,
        submitted_by=row.submitted_by,
        created_at=row.created_at,
        company_name=job.company_name,
        total_score=total_score,
        priority_band=priority_band,
    )


@router.get(
    "/prospects/{job_id}/feedback",
    response_model=list[FeedbackRecord],
    tags=["feedback"],
)
async def get_job_feedback(
    job_id: str,
    session: SessionDep,
) -> list[FeedbackRecord]:
    """Retrieve all feedback submissions for a specific job."""
    job = await get_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    rows = await StorageAdapter.get_feedback_by_job(session, job_id)

    total_score = None
    priority_band = None
    if job.score_json:
        try:
            score_data = json.loads(job.score_json)
            total_score = score_data.get("total")
            priority_band = score_data.get("band")
        except Exception:
            pass

    return [
        FeedbackRecord(
            feedback_id=r.feedback_id,
            job_id=r.job_id,
            score_accuracy=r.score_accuracy,
            brief_quality=r.brief_quality,
            outreach_quality=r.outreach_quality,
            comment=r.comment,
            submitted_by=r.submitted_by,
            created_at=r.created_at,
            company_name=job.company_name,
            total_score=total_score,
            priority_band=priority_band,
        )
        for r in rows
    ]


@router.get(
    "/feedback",
    response_model=list[FeedbackRecord],
    tags=["feedback"],
)
async def list_all_feedback(session: SessionDep) -> list[FeedbackRecord]:
    """List all feedback across all jobs joined with company_name and lead score."""
    records = await StorageAdapter.get_all_feedback(session)
    return [FeedbackRecord(**rec) for rec in records]


# Rendering helpers


def _brief_to_markdown(brief: ResearchBrief) -> str:
    lines = [
        f"# Research Brief — {brief.snapshot.get('company_name', 'Unknown')}",
        f"*Generated: {brief.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
        "## Snapshot",
        *[f"- **{k}:** {v}" for k, v in brief.snapshot.items()],
        "",
        "## Lead Score",
        f"**Total:** {brief.lead_score.total}/100  |  **Band:** {brief.lead_score.band}",
        f"*Rubric version: {brief.lead_score.rubric_version}*",
        "",
        "| Factor | Weight | Points | Evidence |",
        "|--------|--------|--------|----------|",
        *[
            f"| {f.factor} | {f.weight} | {f.points_awarded} | {f.evidence} |"
            for f in brief.lead_score.breakdown
        ],
        "",
        "## Contact / Decision-Makers",
        *[f"- **{k}:** {v}" for k, v in brief.contact.items()],
        "",
        "## Company Research",
        *[f"- **{k}:** {v}" for k, v in brief.company_research.items()],
        "",
        "## Projects & Buying Signals",
        *[f"- [{f.label.value}] {f.field}: {f.value}" for f in brief.projects_signals],
        "",
        "## Likely Requirements *(hypothesis)*",
        *[f"- [{f.label.value}] {f.value}" for f in brief.likely_requirements],
        "",
        "## Pain-Point Hypotheses *(hypothesis — not confirmed)*",
        *[f"- [{f.label.value}] {f.value}" for f in brief.pain_point_hypotheses],
        "",
        "## Recommended Approach",
        f"{brief.recommended_approach.summary}",
        f"*Angle:* {brief.recommended_approach.angle or 'N/A'}",
        "",
        "## Risks & Unknowns",
        *[f"- {r}" for r in brief.risks_unknowns],
        "",
        "## Next Action",
        f"**{brief.next_action.action}**",
        f"Owner: {brief.next_action.owner or 'N/A'}",
        "",
        "## Sources",
        *[
            f"- [{s.title or s.url}]({s.url})"
            + (f" *(reviewed {s.date_reviewed})*" if s.date_reviewed else "")
            for s in brief.sources
        ],
    ]
    return "\n".join(lines)


def _crm_to_csv(record: CRMExportRecord) -> str:
    import csv
    import io

    buf = io.StringIO()
    flat = {
        "job_id": record.job_id,
        "lead_score_total": record.lead_score_total,
        "lead_score_band": record.lead_score_band,
        "possible_duplicate": record.possible_duplicate,
        "exported_at": str(record.exported_at),
    }
    flat.update({f"company_{k}": v for k, v in record.company_fields.items()})
    flat.update({f"contact_{k}": v for k, v in record.contact_fields.items()})
    flat.update({f"deal_{k}": v for k, v in record.deal_fields.items()})

    writer = csv.DictWriter(buf, fieldnames=flat.keys())
    writer.writeheader()
    writer.writerow(flat)
    return buf.getvalue()
