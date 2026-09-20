"""
Database Models, Initialization, and Storage Layer for SQLite.
Implements the full normalized relational schema per design.md:
  - jobs
  - findings
  - lead_scores
  - briefs
  - crm_exports
  - outreach_drafts
  - SQL views for easy analysis in DB Browser for SQLite
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, relationship

from config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ORM Models

class JobRow(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending")
    company_name = Column(String, nullable=False)
    website = Column(String, nullable=False)
    known_contact_name = Column(String, nullable=True)
    known_contact_title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))
    error_message = Column(Text, nullable=True)

    # Legacy JSON columns kept for backward compatibility with existing tests
    findings_json = Column(Text, nullable=True)
    score_json = Column(Text, nullable=True)
    brief_json = Column(Text, nullable=True)
    outreach_json = Column(Text, nullable=True)
    crm_export_json = Column(Text, nullable=True)
    proposal_json = Column(Text, nullable=True)

    # Relationships
    findings = relationship("FindingRow", back_populates="job", cascade="all, delete-orphan")
    score = relationship("LeadScoreRow", back_populates="job", uselist=False, cascade="all, delete-orphan")
    brief = relationship("BriefRow", back_populates="job", uselist=False, cascade="all, delete-orphan")
    crm_export = relationship("CRMExportRow", back_populates="job", uselist=False, cascade="all, delete-orphan")
    outreach = relationship("OutreachRow", back_populates="job", uselist=False, cascade="all, delete-orphan")
    feedback = relationship("FeedbackRow", back_populates="job", cascade="all, delete-orphan")


class FeedbackRow(Base):
    __tablename__ = "feedback"

    feedback_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    score_accuracy = Column(String, nullable=False)  # too_low, about_right, too_high
    brief_quality = Column(String, nullable=False)   # poor, okay, good
    outreach_quality = Column(String, nullable=False, default="not_applicable")  # poor, okay, good, not_applicable
    comment = Column(Text, nullable=True)
    submitted_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("JobRow", back_populates="feedback")


class FindingRow(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False, default="snapshot")  # snapshot, decision_maker, signal, missing
    field = Column(String, nullable=False)
    value = Column(Text, nullable=False)
    label = Column(String, nullable=False, default="Unverified")  # Verified, Probable, Unverified
    sources_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("JobRow", back_populates="findings")


class LeadScoreRow(Base):
    __tablename__ = "lead_scores"

    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), primary_key=True)
    rubric_version = Column(String, nullable=False, default="v1.0")
    total_score = Column(Integer, nullable=False)
    priority_band = Column(String, nullable=False)  # High, Medium, Low
    breakdown_json = Column(Text, nullable=False)
    zero_evidence_factors_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("JobRow", back_populates="score")


class BriefRow(Base):
    __tablename__ = "briefs"

    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), primary_key=True)
    snapshot_json = Column(Text, nullable=True)
    contact_json = Column(Text, nullable=True)
    company_research_json = Column(Text, nullable=True)
    projects_signals_json = Column(Text, nullable=True)
    likely_requirements_json = Column(Text, nullable=True)
    pain_hypotheses_json = Column(Text, nullable=True)
    recommended_approach_json = Column(Text, nullable=True)
    commercial_risks_json = Column(Text, nullable=True)
    next_action_json = Column(Text, nullable=True)
    sources_json = Column(Text, nullable=True)
    rendered_markdown = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("JobRow", back_populates="brief")


class CRMExportRow(Base):
    __tablename__ = "crm_exports"

    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), primary_key=True)
    company_name = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    score = Column(Integer, nullable=False)
    priority_band = Column(String, nullable=False)
    lead_status = Column(String, nullable=False, default="NEW_LEAD")
    verified_contact_name = Column(String, nullable=True)
    verified_contact_title = Column(String, nullable=True)
    recommended_service = Column(String, nullable=True)
    possible_duplicate = Column(Boolean, default=False)
    hubspot_payload_json = Column(Text, nullable=True)
    csv_row_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("JobRow", back_populates="crm_export")


class OutreachRow(Base):
    __tablename__ = "outreach_drafts"

    job_id = Column(String, ForeignKey("jobs.job_id", ondelete="CASCADE"), primary_key=True)
    email_touch_1 = Column(Text, nullable=True)
    email_touch_2 = Column(Text, nullable=True)
    email_touch_3 = Column(Text, nullable=True)
    linkedin_connection = Column(Text, nullable=True)
    linkedin_pitch = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    job = relationship("JobRow", back_populates="outreach")


# Database Initialization & View Setup

VIEW_SQLS = [
    """
    CREATE VIEW IF NOT EXISTS vw_jobs_by_score_desc AS
    SELECT 
        j.job_id,
        j.company_name,
        j.website,
        j.status,
        s.total_score,
        s.priority_band,
        s.rubric_version,
        j.created_at
    FROM jobs j
    LEFT JOIN lead_scores s ON j.job_id = s.job_id
    ORDER BY s.total_score DESC NULLS LAST, j.created_at DESC;
    """,
    """
    CREATE VIEW IF NOT EXISTS vw_jobs_by_band AS
    SELECT 
        COALESCE(s.priority_band, 'Unscored / Failed') AS priority_band,
        COUNT(*) AS count,
        ROUND(AVG(s.total_score), 1) AS avg_score,
        MIN(s.total_score) AS min_score,
        MAX(s.total_score) AS max_score
    FROM jobs j
    LEFT JOIN lead_scores s ON j.job_id = s.job_id
    GROUP BY COALESCE(s.priority_band, 'Unscored / Failed')
    ORDER BY avg_score DESC NULLS LAST;
    """,
    """
    CREATE VIEW IF NOT EXISTS vw_failed_jobs AS
    SELECT 
        job_id,
        company_name,
        website,
        status,
        error_message,
        created_at,
        updated_at
    FROM jobs
    WHERE status LIKE 'failed%' OR error_message IS NOT NULL
    ORDER BY updated_at DESC;
    """,
    """
    CREATE VIEW IF NOT EXISTS vw_feedback_overview AS
    SELECT 
        f.feedback_id,
        f.job_id,
        j.company_name,
        j.website,
        s.total_score,
        s.priority_band,
        f.score_accuracy,
        f.brief_quality,
        f.outreach_quality,
        f.comment,
        f.submitted_by,
        f.created_at
    FROM feedback f
    JOIN jobs j ON f.job_id = j.job_id
    LEFT JOIN lead_scores s ON f.job_id = s.job_id
    ORDER BY f.created_at DESC;
    """
]


async def init_db() -> None:
    """Initialize tables and pre-written views in SQLite."""
    import os
    from pathlib import Path
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
        if db_path and not db_path.startswith(":memory:"):
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migrate schema if proposal_json is missing on existing SQLite db
        try:
            await conn.execute(text("ALTER TABLE jobs ADD COLUMN proposal_json TEXT;"))
        except Exception:
            pass
        for view_sql in VIEW_SQLS:
            await conn.execute(text(view_sql))
    logger.info("Database initialized with 7 tables and 4 views.")




async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


# Clean Storage Adapter Interface

class StorageAdapter:
    """Clean storage interface for all pipeline persistence operations."""

    @staticmethod
    async def create_job(
        session: AsyncSession,
        job_id: str,
        company_name: str,
        website: str,
        known_contact_name: Optional[str] = None,
        known_contact_title: Optional[str] = None,
    ) -> JobRow:
        now = datetime.now(UTC)
        row = JobRow(
            job_id=job_id,
            status="pending",
            company_name=company_name,
            website=website,
            known_contact_name=known_contact_name,
            known_contact_title=known_contact_title,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        return row

    @staticmethod
    async def get_job(session: AsyncSession, job_id: str) -> Optional[JobRow]:
        result = await session.execute(select(JobRow).where(JobRow.job_id == job_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_job_status(
        session: AsyncSession,
        job_id: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        values: dict = {"status": status, "updated_at": datetime.now(UTC)}
        if error_message is not None:
            values["error_message"] = error_message
        await session.execute(update(JobRow).where(JobRow.job_id == job_id).values(**values))
        await session.commit()

    @staticmethod
    async def save_findings(session: AsyncSession, job_id: str, findings_dict: dict) -> None:
        # Also save legacy JSON column for backward compatibility
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(findings_json=json.dumps(findings_dict), updated_at=datetime.now(UTC))
        )
        # Populate normalized findings rows
        # Remove existing if re-running
        await session.execute(text("DELETE FROM findings WHERE job_id = :jid"), {"jid": job_id})
        
        findings_rows = []
        for category, items in [
            ("snapshot", findings_dict.get("company_snapshot", [])),
            ("decision_maker", findings_dict.get("decision_makers", [])),
            ("signal", findings_dict.get("projects_signals", [])),
        ]:
            for item in items:
                sources = item.get("sources", [])
                if not sources and item.get("source_urls"):
                    sources = [{"url": u} for u in item.get("source_urls")]
                findings_rows.append(FindingRow(
                    job_id=job_id,
                    category=category,
                    field=item.get("field", "unknown"),
                    value=str(item.get("value", "")),
                    label=item.get("label", "Unverified"),
                    sources_json=json.dumps(sources),
                ))
        for note in findings_dict.get("notes_missing", []):
            findings_rows.append(FindingRow(
                job_id=job_id,
                category="missing",
                field="missing_evidence",
                value=str(note),
                label="Unverified",
                sources_json="[]",
            ))
        if findings_rows:
            session.add_all(findings_rows)
        await session.commit()

    @staticmethod
    async def save_lead_score(session: AsyncSession, job_id: str, score_dict: dict) -> None:
        # Save legacy JSON
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(score_json=json.dumps(score_dict, default=str), updated_at=datetime.now(UTC))
        )
        # Normalized table
        await session.execute(text("DELETE FROM lead_scores WHERE job_id = :jid"), {"jid": job_id})
        score_row = LeadScoreRow(
            job_id=job_id,
            rubric_version=score_dict.get("rubric_version", "v1.0"),
            total_score=score_dict.get("total", 0),
            priority_band=score_dict.get("band", "Low"),
            breakdown_json=json.dumps(score_dict.get("breakdown", []), default=str),
            zero_evidence_factors_json=json.dumps(score_dict.get("zero_evidence_factors", []), default=str),
        )
        session.add(score_row)
        await session.commit()

    @staticmethod
    async def save_brief(session: AsyncSession, job_id: str, brief_dict: dict) -> None:
        # Save legacy JSON
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(brief_json=json.dumps(brief_dict, default=str), updated_at=datetime.now(UTC))
        )
        # Normalized table
        await session.execute(text("DELETE FROM briefs WHERE job_id = :jid"), {"jid": job_id})
        brief_row = BriefRow(
            job_id=job_id,
            snapshot_json=json.dumps(brief_dict.get("snapshot", {}), default=str),
            contact_json=json.dumps(brief_dict.get("contact", {}), default=str),
            company_research_json=json.dumps(brief_dict.get("company_research", {}), default=str),
            projects_signals_json=json.dumps(brief_dict.get("projects_signals", []), default=str),
            likely_requirements_json=json.dumps(brief_dict.get("likely_requirements", []), default=str),
            pain_hypotheses_json=json.dumps(brief_dict.get("pain_point_hypotheses", []), default=str),
            recommended_approach_json=json.dumps(brief_dict.get("recommended_approach", {}), default=str),
            commercial_risks_json=json.dumps(brief_dict.get("commercial_risks", []), default=str),
            next_action_json=json.dumps(brief_dict.get("next_action", {}), default=str),
            sources_json=json.dumps(brief_dict.get("sources", []), default=str),
        )
        session.add(brief_row)
        await session.commit()

    @staticmethod
    async def save_crm_export(session: AsyncSession, job_id: str, crm_dict: dict) -> None:
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(crm_export_json=json.dumps(crm_dict), updated_at=datetime.now(UTC))
        )
        await session.execute(text("DELETE FROM crm_exports WHERE job_id = :jid"), {"jid": job_id})
        crm_row = CRMExportRow(
            job_id=job_id,
            company_name=crm_dict.get("company_name", ""),
            domain=crm_dict.get("domain", ""),
            score=crm_dict.get("score", 0),
            priority_band=crm_dict.get("priority_band", "Low"),
            lead_status=crm_dict.get("lead_status", "NEW_LEAD"),
            verified_contact_name=crm_dict.get("verified_contact_name"),
            verified_contact_title=crm_dict.get("verified_contact_title"),
            recommended_service=crm_dict.get("recommended_service"),
            possible_duplicate=crm_dict.get("possible_duplicate", False),
            hubspot_payload_json=json.dumps(crm_dict.get("hubspot_payload", {})),
            csv_row_text=crm_dict.get("csv_row_text", ""),
        )
        session.add(crm_row)
        await session.commit()

    @staticmethod
    async def save_outreach(session: AsyncSession, job_id: str, outreach_dict: dict) -> None:
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(outreach_json=json.dumps(outreach_dict), updated_at=datetime.now(UTC))
        )
        await session.execute(text("DELETE FROM outreach_drafts WHERE job_id = :jid"), {"jid": job_id})
        outreach_row = OutreachRow(
            job_id=job_id,
            email_touch_1=outreach_dict.get("email_touch_1"),
            email_touch_2=outreach_dict.get("email_touch_2"),
            email_touch_3=outreach_dict.get("email_touch_3"),
            linkedin_connection=outreach_dict.get("linkedin_connection"),
            linkedin_pitch=outreach_dict.get("linkedin_pitch"),
            status=outreach_dict.get("status", "draft"),
        )
        session.add(outreach_row)
        await session.commit()

    @staticmethod
    async def save_feedback(session: AsyncSession, job_id: str, feedback_data: dict) -> FeedbackRow:
        row = FeedbackRow(
            job_id=job_id,
            score_accuracy=feedback_data["score_accuracy"],
            brief_quality=feedback_data["brief_quality"],
            outreach_quality=feedback_data.get("outreach_quality", "not_applicable"),
            comment=feedback_data.get("comment"),
            submitted_by=feedback_data.get("submitted_by"),
            created_at=datetime.now(UTC),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row

    @staticmethod
    async def get_feedback_by_job(session: AsyncSession, job_id: str) -> list[FeedbackRow]:
        result = await session.execute(
            select(FeedbackRow)
            .where(FeedbackRow.job_id == job_id)
            .order_by(FeedbackRow.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_all_feedback(session: AsyncSession) -> list[dict]:
        stmt = (
            select(
                FeedbackRow,
                JobRow.company_name,
                LeadScoreRow.total_score,
                LeadScoreRow.priority_band,
            )
            .join(JobRow, FeedbackRow.job_id == JobRow.job_id)
            .outerjoin(LeadScoreRow, FeedbackRow.job_id == LeadScoreRow.job_id)
            .order_by(FeedbackRow.created_at.desc())
        )
        result = await session.execute(stmt)
        records = []
        for fb_row, company_name, total_score, priority_band in result.all():
            records.append({
                "feedback_id": fb_row.feedback_id,
                "job_id": fb_row.job_id,
                "score_accuracy": fb_row.score_accuracy,
                "brief_quality": fb_row.brief_quality,
                "outreach_quality": fb_row.outreach_quality,
                "comment": fb_row.comment,
                "submitted_by": fb_row.submitted_by,
                "created_at": fb_row.created_at,
                "company_name": company_name,
                "total_score": total_score,
                "priority_band": priority_band,
            })
        return records

    @staticmethod
    async def save_proposal(session: AsyncSession, job_id: str, proposal_dict: dict) -> None:
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(proposal_json=json.dumps(proposal_dict), updated_at=datetime.now(UTC))
        )
        await session.commit()


# Backward-compatible function helpers

async def create_job(session: AsyncSession, row: JobRow) -> None:
    session.add(row)
    await session.commit()


async def get_job(session: AsyncSession, job_id: str) -> JobRow | None:
    return await StorageAdapter.get_job(session, job_id)


async def update_job_status(
    session: AsyncSession,
    job_id: str,
    status: str,
    error_message: str | None = None,
) -> None:
    await StorageAdapter.update_job_status(session, job_id, status, error_message)


async def save_json_field(
    session: AsyncSession, job_id: str, field: str, data: dict
) -> None:
    if field == "findings_json":
        await StorageAdapter.save_findings(session, job_id, data)
    elif field == "score_json":
        await StorageAdapter.save_lead_score(session, job_id, data)
    elif field == "brief_json":
        await StorageAdapter.save_brief(session, job_id, data)
    elif field == "crm_export_json":
        await StorageAdapter.save_crm_export(session, job_id, data)
    elif field == "outreach_json":
        await StorageAdapter.save_outreach(session, job_id, data)
    elif field == "proposal_json":
        await StorageAdapter.save_proposal(session, job_id, data)
    else:
        await session.execute(
            update(JobRow)
            .where(JobRow.job_id == job_id)
            .values(**{field: json.dumps(data), "updated_at": datetime.now(UTC)})
        )
        await session.commit()


async def find_recent_job(
    session: AsyncSession,
    company_name: str,
    website: str,
    within_hours: int,
) -> JobRow | None:
    cutoff = datetime.now(UTC) - timedelta(hours=within_hours)
    incoming_domain = urlparse(website).netloc.lower().lstrip("www.")

    result = await session.execute(
        select(JobRow)
        .where(JobRow.created_at >= cutoff)
        .order_by(JobRow.created_at.desc())
    )
    rows = result.scalars().all()

    for row in rows:
        row_domain = urlparse(row.website).netloc.lower().lstrip("www.")
        name_match = row.company_name.lower().strip() == company_name.lower().strip()
        domain_match = row_domain == incoming_domain and incoming_domain != ""
        if name_match or domain_match:
            return row

    return None