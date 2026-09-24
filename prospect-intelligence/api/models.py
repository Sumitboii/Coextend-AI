"""
Core Pydantic v2 data models for the Coextend Prospect Intelligence MVP.
These schemas are the single source of truth for validation, serialisation,
and documentation across the API, engine, scoring, and brief-generation layers.
"""
from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


# Intake

class ProspectRequest(BaseModel):
    """Submitted by a salesperson to trigger a research job."""

    company_name: str = Field(..., min_length=1, max_length=255)
    website: AnyHttpUrl
    known_contact_name: str | None = Field(None, max_length=255)
    known_contact_title: str | None = Field(None, max_length=255)

    @field_validator("company_name")
    @classmethod
    def strip_company_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("company_name cannot be empty or whitespace-only.")
        return stripped


class JobStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"
    SCORING = "scoring"
    DRAFTING = "drafting"
    COMPLETE = "complete"
    FAILED = "failed"


class JobRecord(BaseModel):
    """Returned immediately after a job is created."""

    job_id: str
    status: JobStatus
    created_at: datetime
    company_name: str
    website: str
    duplicate_warning: bool = False
    error_message: str | None = None


# Evidence primitives

class EvidenceLabel(str, Enum):
    VERIFIED = "Verified"
    PROBABLE = "Probable"
    UNVERIFIED = "Unverified"


class SourceRef(BaseModel):
    """A single source citation attached to a finding."""

    url: AnyHttpUrl
    title: str | None = None
    date_reviewed: date | None = None


class Finding(BaseModel):
    """One discrete research fact with its evidence label and sources."""

    field: str = Field(..., description="Logical field name, e.g. 'company_size'")
    value: str
    label: EvidenceLabel
    sources: list[SourceRef] = Field(default_factory=list)


# Research findings (external research layer)

class ResearchFindings(BaseModel):
    """All structured findings for one prospect, produced by the Research Engine."""

    job_id: str
    company_snapshot: list[Finding] = Field(default_factory=list)
    decision_makers: list[Finding] = Field(default_factory=list)
    projects_signals: list[Finding] = Field(default_factory=list)
    # Explicit "no evidence found" entries Ã¢â‚¬â€ never silently omitted
    notes_missing: list[str] = Field(default_factory=list)
    # Sources rejected during verification — visible in audit trail
    sources_rejected: list[str] = Field(default_factory=list, description="Sources excluded because they don't match the searched company")


# Lead scoring

class ScoreFactor(BaseModel):
    """One row in the scoring breakdown."""

    factor: str
    weight: int = Field(..., ge=0, le=100)
    points_awarded: int = Field(..., ge=0)
    evidence: str


class LeadScore(BaseModel):
    """Deterministic 0Ã¢â‚¬â€œ100 score with full breakdown."""

    rubric_version: str
    total: int = Field(..., ge=0, le=100)
    band: Literal[
        "A+ / Priority",
        "A / Strong fit",
        "B / Nurture",
        "C / Low priority",
        "D / Disqualify",
    ]
    breakdown: list[ScoreFactor]
    # Req 4.5, 4.7 Ã¢â‚¬â€ factors that scored 0 because their finding field was absent
    zero_evidence_factors: list[str] = Field(default_factory=list)


# Research brief (output of Brief Generator)

class RecommendedApproach(BaseModel):
    summary: str
    angle: str | None = None
    key_capabilities_to_lead_with: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)


class NextAction(BaseModel):
    action: str
    owner: str | None = None
    notes: str | None = None


class KnowledgeCitation(BaseModel):
    """Maps a statement in the brief back to its source Knowledge_Chunk (Req. 3.5)."""

    statement: str = Field(..., description="The statement in the brief derived from internal knowledge")
    source_document: str = Field(..., description="The source PDF document name")
    section: str | None = Field(None, description="The section within the document")


class ResearchBrief(BaseModel):
    """Complete founder-ready research brief for one prospect."""

    job_id: str
    # Snapshot section
    snapshot: dict = Field(default_factory=dict)
    # Contact/decision-maker section
    contact: dict = Field(default_factory=dict)
    # Company research section
    company_research: dict = Field(default_factory=dict)
    # Projects and buying signals
    projects_signals: list[Finding] = Field(default_factory=list)
    # Likely requirements (presented as hypotheses)
    likely_requirements: list[Finding] = Field(default_factory=list)
    # Pain-point hypotheses Ã¢â‚¬â€ explicitly labelled as hypotheses
    pain_point_hypotheses: list[Finding] = Field(default_factory=list)
    # Deterministic score
    lead_score: LeadScore
    # Recommended approach (grounded in internal knowledge)
    recommended_approach: RecommendedApproach
    # Risks / unknowns
    risks_unknowns: list[str] = Field(default_factory=list)
    # Next action
    next_action: NextAction
    # All source URLs used
    sources: list[SourceRef] = Field(default_factory=list)
    # Citations mapping brief statements to their Knowledge_Chunk origins (Req. 3.5)
    knowledge_citations: list[KnowledgeCitation] = Field(default_factory=list)
    # Set to True when the post-generation label-escalation check could not run (Req. 10.7)
    validation_skipped: bool = False
    # Generation metadata
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Outreach drafts

class OutreachDrafts(BaseModel):
    """Email + LinkedIn drafts Ã¢â‚¬â€ multi-touch cadence per 05 - Follow Up Messages.docx."""

    job_id: str
    email_subject: str = ""
    email_body: str = ""  # Primary cold email (Touch 1) for backward compatibility
    email_touch_1: str = ""  # Touch 1: Pain Observation & Specific Project Trigger
    email_touch_2: str = ""  # Touch 2: Soft Capability Bump (Day 3-4)
    email_touch_3: str = ""  # Touch 3: Low-Friction Value-Add / Breakup (Day 7-8)
    linkedin_message: str = ""  # Primary LinkedIn connection request (<300 chars)
    linkedin_connection: str = ""  # Explicit LinkedIn connection note
    linkedin_pitch: str = ""  # Follow-up LinkedIn pitch message post-connection
    # Always "draft"; the system NEVER changes this to anything else
    status: Literal["draft"] = "draft"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    review_note: str = "draft — requires human review before use"

    def model_post_init(self, __context) -> None:
        # Keep backward compatibility aliases synchronized
        if not self.email_touch_1 and self.email_body:
            self.email_touch_1 = self.email_body
        elif self.email_touch_1 and not self.email_body:
            self.email_body = self.email_touch_1
        
        if not self.linkedin_connection and self.linkedin_message:
            self.linkedin_connection = self.linkedin_message
        elif self.linkedin_connection and not self.linkedin_message:
            self.linkedin_message = self.linkedin_connection


# CRM export

class CRMExportRecord(BaseModel):
    """HubSpot-style record for one completed research job."""

    job_id: str
    # HubSpot company properties
    company_fields: dict = Field(default_factory=dict)
    # HubSpot contact properties
    contact_fields: dict = Field(default_factory=dict)
    # HubSpot deal properties
    deal_fields: dict = Field(default_factory=dict)
    lead_score_total: int = Field(..., ge=0, le=100)
    lead_score_band: str
    possible_duplicate: bool = False
    exported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))



# Feedback

class FeedbackCreate(BaseModel):
    """Submitted by a user/salesperson to review scoring & brief quality."""

    score_accuracy: Literal["too_low", "about_right", "too_high"]
    brief_quality: Literal["poor", "okay", "good"]
    outreach_quality: Literal["poor", "okay", "good", "not_applicable"] = "not_applicable"
    comment: str | None = Field(None, max_length=2000)
    submitted_by: str | None = Field(None, max_length=100)


class FeedbackRecord(BaseModel):
    """Feedback item returned by API."""

    feedback_id: int
    job_id: str
    score_accuracy: str
    brief_quality: str
    outreach_quality: str
    comment: str | None = None
    submitted_by: str | None = None
    created_at: datetime
    company_name: str | None = None
    total_score: int | None = None
    priority_band: str | None = None


# Proposal Drafts (08 - Proposal Templates.docx)

class ProposalDraft(BaseModel):
    """Tailored Scope of Work proposal draft generated from 08 template."""

    job_id: str
    proposal_title: str
    client_requirement: str
    proposed_scope: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    turnaround_programme: str
    commercial_options: list[dict] = Field(default_factory=list)
    assumptions_exclusions: list[str] = Field(default_factory=list)
    pilot_option: str
    rendered_markdown: str
    status: Literal["draft"] = "draft"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))




