"""
Task 2 — Schema validation unit tests.
Tests required fields, URL validation, enum constraints, and validation rules.
Validates: Requirements 1.2, 3.6, 4.1, 5.1, 6.1, 7.5
"""
import pytest
from datetime import UTC, datetime, date
from pydantic import ValidationError

from api.models import (
    CRMExportRecord,
    EvidenceLabel,
    Finding,
    JobRecord,
    JobStatus,
    LeadScore,
    OutreachDrafts,
    ProspectRequest,
    ResearchBrief,
    ResearchFindings,
    ScoreFactor,
    SourceRef,
    FeedbackCreate,
    FeedbackRecord,
    RecommendedApproach,
    NextAction,
    KnowledgeCitation,
    ProposalDraft,
)


class TestProspectRequest:
    """Tests for ProspectRequest model — Req 1.2 (required fields, URL validation)."""
    
    def test_valid_minimal(self):
        req = ProspectRequest(company_name="Harley Facades", website="https://harleyfacades.com")
        assert req.company_name == "Harley Facades"

    def test_valid_with_contact(self):
        req = ProspectRequest(
            company_name="Test Co",
            website="https://test.com",
            known_contact_name="Jane Smith",
            known_contact_title="MD",
        )
        assert req.known_contact_name == "Jane Smith"

    def test_missing_company_name(self):
        """Required field: company_name must be provided."""
        with pytest.raises(ValidationError):
            ProspectRequest(website="https://test.com")

    def test_missing_website(self):
        """Required field: website must be provided."""
        with pytest.raises(ValidationError):
            ProspectRequest(company_name="Test Co")

    def test_invalid_url(self):
        """URL validation: rejects invalid URLs."""
        with pytest.raises(ValidationError):
            ProspectRequest(company_name="Test Co", website="not-a-url")

    def test_empty_company_name(self):
        """String length constraint: company_name must have min_length=1."""
        with pytest.raises(ValidationError):
            ProspectRequest(company_name="", website="https://test.com")

    def test_company_name_max_length(self):
        """String length constraint: company_name max_length=255."""
        long_name = "A" * 256
        with pytest.raises(ValidationError):
            ProspectRequest(company_name=long_name, website="https://test.com")

    def test_company_name_max_length_valid(self):
        """Company name exactly at max length (255) is valid."""
        long_name = "A" * 255
        req = ProspectRequest(company_name=long_name, website="https://test.com")
        assert len(req.company_name) == 255

    def test_company_name_stripped(self):
        """Auto-stripping: whitespace trimmed from company_name."""
        req = ProspectRequest(company_name="  Acme  ", website="https://acme.com")
        assert req.company_name == "Acme"

    def test_company_name_leading_trailing_tabs(self):
        """Auto-stripping: tabs and mixed whitespace trimmed."""
        req = ProspectRequest(company_name="\t  Acme Corp  \n", website="https://acme.com")
        assert req.company_name == "Acme Corp"

    def test_contact_name_max_length(self):
        """String length constraint: known_contact_name max_length=255."""
        long_name = "A" * 256
        with pytest.raises(ValidationError):
            ProspectRequest(
                company_name="Test",
                website="https://test.com",
                known_contact_name=long_name
            )

    def test_contact_title_max_length(self):
        """String length constraint: known_contact_title max_length=255."""
        long_title = "A" * 256
        with pytest.raises(ValidationError):
            ProspectRequest(
                company_name="Test",
                website="https://test.com",
                known_contact_title=long_title
            )

    def test_contact_fields_optional(self):
        """Optional fields: known_contact_name and known_contact_title can be None."""
        req = ProspectRequest(company_name="Test", website="https://test.com")
        assert req.known_contact_name is None
        assert req.known_contact_title is None

    def test_various_valid_urls(self):
        """URL validation: accepts various valid URL formats."""
        test_urls = [
            "https://example.com",
            "http://example.com",
            "https://www.example.com",
            "https://example.com/path",
            "https://example.com:8080",
            "https://sub.example.co.uk",
        ]
        for url in test_urls:
            req = ProspectRequest(company_name="Test", website=url)
            assert req.website is not None


class TestJobStatus:
    """Tests for JobStatus enum."""
    
    def test_valid_statuses(self):
        """Enum constraint: only valid status values accepted."""
        statuses = ["pending", "researching", "scoring", "drafting", "complete", "failed"]
        for status in statuses:
            assert JobStatus(status).value == status

    def test_invalid_status(self):
        """Enum constraint: invalid status rejected."""
        with pytest.raises(ValueError):
            JobStatus("unknown_status")


class TestJobRecord:
    """Tests for JobRecord model."""
    
    def test_valid_record(self):
        """Valid job record with all required fields."""
        now = datetime.now(UTC)
        record = JobRecord(
            job_id="job123",
            status=JobStatus.PENDING,
            created_at=now,
            company_name="Test Co",
            website="https://test.com"
        )
        assert record.job_id == "job123"
        assert record.status == JobStatus.PENDING

    def test_missing_required_fields(self):
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            JobRecord(job_id="job123")

    def test_duplicate_warning_default(self):
        """Optional field: duplicate_warning defaults to False."""
        now = datetime.now(UTC)
        record = JobRecord(
            job_id="job123",
            status=JobStatus.PENDING,
            created_at=now,
            company_name="Test Co",
            website="https://test.com"
        )
        assert record.duplicate_warning is False

    def test_error_message_optional(self):
        """Optional field: error_message can be None."""
        now = datetime.now(UTC)
        record = JobRecord(
            job_id="job123",
            status=JobStatus.PENDING,
            created_at=now,
            company_name="Test Co",
            website="https://test.com",
            error_message=None
        )
        assert record.error_message is None

    def test_error_message_with_value(self):
        """Optional field: error_message can have value."""
        now = datetime.now(UTC)
        record = JobRecord(
            job_id="job123",
            status=JobStatus.FAILED,
            created_at=now,
            company_name="Test Co",
            website="https://test.com",
            error_message="Connection timeout"
        )
        assert record.error_message == "Connection timeout"


class TestEvidenceLabel:
    """Tests for EvidenceLabel enum — Req 3.6 (enum constraints)."""
    
    def test_valid_labels(self):
        """Enum constraint: only 'Verified', 'Probable', 'Unverified' allowed."""
        for label in ("Verified", "Probable", "Unverified"):
            assert EvidenceLabel(label).value == label

    def test_invalid_label(self):
        """Enum constraint: invalid label rejected."""
        with pytest.raises(ValueError):
            EvidenceLabel("Confirmed")

    def test_invalid_label_lowercase(self):
        """Enum constraint: case-sensitive — lowercase rejected."""
        with pytest.raises(ValueError):
            EvidenceLabel("verified")

    def test_enum_values(self):
        """Verify exact enum values."""
        assert EvidenceLabel.VERIFIED.value == "Verified"
        assert EvidenceLabel.PROBABLE.value == "Probable"
        assert EvidenceLabel.UNVERIFIED.value == "Unverified"


class TestSourceRef:
    """Tests for SourceRef model — Req 1.2 (URL validation)."""
    
    def test_valid_with_all_fields(self):
        """Valid source ref with all fields."""
        s = SourceRef(
            url="https://example.com",
            title="Home Page",
            date_reviewed=date(2024, 1, 15)
        )
        assert s.title == "Home Page"
        assert s.date_reviewed == date(2024, 1, 15)

    def test_valid_minimal(self):
        """Valid source ref with only URL."""
        s = SourceRef(url="https://example.com")
        assert s.url is not None

    def test_invalid_url(self):
        """URL validation: rejects invalid URLs."""
        with pytest.raises(ValidationError):
            SourceRef(url="not-a-url")

    def test_invalid_url_no_protocol(self):
        """URL validation: rejects URLs without protocol."""
        with pytest.raises(ValidationError):
            SourceRef(url="example.com")

    def test_title_optional(self):
        """Optional field: title can be None."""
        s = SourceRef(url="https://example.com", title=None)
        assert s.title is None

    def test_date_optional(self):
        """Optional field: date_reviewed can be None."""
        s = SourceRef(url="https://example.com", date_reviewed=None)
        assert s.date_reviewed is None

    def test_various_valid_urls(self):
        """URL validation: accepts various valid URL formats."""
        urls = [
            "https://example.com",
            "http://example.com",
            "https://www.example.co.uk/path?query=1",
            "https://sub.example.com:8080",
        ]
        for url in urls:
            s = SourceRef(url=url)
            assert s.url is not None


class TestFinding:
    """Tests for Finding model."""
    
    def test_valid_finding(self):
        """Valid finding with all fields."""
        f = Finding(
            field="trade_fit",
            value="facade contractor",
            label=EvidenceLabel.VERIFIED,
            sources=[SourceRef(url="https://example.com")]
        )
        assert f.label == EvidenceLabel.VERIFIED
        assert len(f.sources) == 1

    def test_valid_minimal(self):
        """Valid finding with minimal fields."""
        f = Finding(field="company_size", value="500-1000", label=EvidenceLabel.PROBABLE)
        assert f.field == "company_size"
        assert len(f.sources) == 0

    def test_invalid_label_string(self):
        """Enum constraint: invalid label string rejected."""
        with pytest.raises(ValidationError):
            Finding(field="x", value="y", label="CONFIRMED")  # type: ignore

    def test_invalid_label_case(self):
        """Enum constraint: case-sensitive — lowercase rejected."""
        with pytest.raises(ValidationError):
            Finding(field="x", value="y", label="verified")  # type: ignore

    def test_sources_default_empty(self):
        """Optional field: sources defaults to empty list."""
        f = Finding(field="x", value="y", label=EvidenceLabel.VERIFIED)
        assert f.sources == []

    def test_multiple_sources(self):
        """Multiple sources can be attached to a finding."""
        sources = [
            SourceRef(url="https://source1.com", title="Source 1"),
            SourceRef(url="https://source2.com", title="Source 2"),
        ]
        f = Finding(field="revenue", value="$50M", label=EvidenceLabel.VERIFIED, sources=sources)
        assert len(f.sources) == 2

    def test_required_field(self):
        """Required field: 'field' must be provided."""
        with pytest.raises(ValidationError):
            Finding(value="y", label=EvidenceLabel.VERIFIED)  # type: ignore

    def test_required_value(self):
        """Required field: 'value' must be provided."""
        with pytest.raises(ValidationError):
            Finding(field="x", label=EvidenceLabel.VERIFIED)  # type: ignore

    def test_required_label(self):
        """Required field: 'label' must be provided."""
        with pytest.raises(ValidationError):
            Finding(field="x", value="y")  # type: ignore


class TestScoreFactor:
    """Tests for ScoreFactor model — Req 4.1 (score ranges)."""
    
    def test_valid_factor(self):
        """Valid score factor with all fields in range."""
        sf = ScoreFactor(
            factor="trade_service_fit",
            weight=20,
            points_awarded=20,
            evidence="facade work"
        )
        assert sf.weight == 20
        assert sf.points_awarded == 20

    def test_weight_range_valid(self):
        """Weight constraint: values 0-100 accepted."""
        for weight in [0, 50, 100]:
            sf = ScoreFactor(
                factor="test",
                weight=weight,
                points_awarded=0,
                evidence="test"
            )
            assert sf.weight == weight

    def test_weight_out_of_range_high(self):
        """Weight constraint: rejects > 100."""
        with pytest.raises(ValidationError):
            ScoreFactor(
                factor="test",
                weight=101,
                points_awarded=0,
                evidence="test"
            )

    def test_weight_out_of_range_low(self):
        """Weight constraint: rejects < 0."""
        with pytest.raises(ValidationError):
            ScoreFactor(
                factor="test",
                weight=-1,
                points_awarded=0,
                evidence="test"
            )

    def test_points_awarded_zero(self):
        """Points awarded: 0 is valid."""
        sf = ScoreFactor(
            factor="test",
            weight=10,
            points_awarded=0,
            evidence="no evidence"
        )
        assert sf.points_awarded == 0

    def test_points_awarded_negative_invalid(self):
        """Points awarded: negative values rejected."""
        with pytest.raises(ValidationError):
            ScoreFactor(
                factor="test",
                weight=10,
                points_awarded=-1,
                evidence="test"
            )

    def test_required_fields(self):
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            ScoreFactor(factor="test")  # type: ignore


class TestLeadScore:
    """Tests for LeadScore model — Req 4.1, 5.1 (score range, band validation)."""
    
    def test_valid_score_a_plus_band(self):
        """Valid score with A+ / Priority band."""
        breakdown = [
            ScoreFactor(factor="test", weight=20, points_awarded=20, evidence="test")
        ]
        score = LeadScore(rubric_version="v1.0", total=85, band="A+ / Priority", breakdown=breakdown)
        assert score.total == 85
        assert score.band == "A+ / Priority"

    def test_valid_score_a_band(self):
        """Valid score with A / Strong fit band."""
        breakdown = [
            ScoreFactor(factor="test", weight=20, points_awarded=15, evidence="test")
        ]
        score = LeadScore(rubric_version="v1.0", total=75, band="A / Strong fit", breakdown=breakdown)
        assert score.total == 75
        assert score.band == "A / Strong fit"

    def test_valid_score_b_band(self):
        """Valid score with B / Nurture band."""
        breakdown = [
            ScoreFactor(factor="test", weight=20, points_awarded=10, evidence="test")
        ]
        score = LeadScore(rubric_version="v1.0", total=55, band="B / Nurture", breakdown=breakdown)
        assert score.band == "B / Nurture"

    def test_valid_score_c_band(self):
        """Valid score with C / Low priority band."""
        breakdown = []
        score = LeadScore(rubric_version="v1.0", total=40, band="C / Low priority", breakdown=breakdown)
        assert score.band == "C / Low priority"

    def test_valid_score_d_band(self):
        """Valid score with D / Disqualify band."""
        breakdown = []
        score = LeadScore(rubric_version="v1.0", total=20, band="D / Disqualify", breakdown=breakdown)
        assert score.band == "D / Disqualify"

    def test_score_boundary_0(self):
        """Score range: 0 is valid."""
        score = LeadScore(rubric_version="v1.0", total=0, band="D / Disqualify", breakdown=[])
        assert score.total == 0

    def test_score_boundary_100(self):
        """Score range: 100 is valid."""
        score = LeadScore(rubric_version="v1.0", total=100, band="A+ / Priority", breakdown=[])
        assert score.total == 100

    def test_score_out_of_range_high(self):
        """Score range: rejects > 100."""
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0", total=101, band="A+ / Priority", breakdown=[])

    def test_negative_score(self):
        """Score range: rejects < 0."""
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0", total=-1, band="D / Disqualify", breakdown=[])

    def test_invalid_band_unknown(self):
        """Band validation: invalid tier name rejected."""
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0", total=50, band="Unknown", breakdown=[])  # type: ignore

    def test_invalid_band_lowercase(self):
        """Band validation: case-sensitive / exact string required."""
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0", total=50, band="a / strong fit", breakdown=[])  # type: ignore

    def test_invalid_band_numeric(self):
        """Band validation: numeric values rejected."""
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0", total=50, band="1", breakdown=[])  # type: ignore

    def test_zero_evidence_factors_default(self):
        """Optional field: zero_evidence_factors defaults to empty list."""
        score = LeadScore(rubric_version="v1.0", total=50, band="B / Nurture", breakdown=[])
        assert score.zero_evidence_factors == []

    def test_zero_evidence_factors_with_values(self):
        """Optional field: zero_evidence_factors can have values."""
        score = LeadScore(
            rubric_version="v1.0",
            total=50,
            band="B / Nurture",
            breakdown=[],
            zero_evidence_factors=["hiring_signals", "compliance"]
        )
        assert len(score.zero_evidence_factors) == 2

    def test_required_fields(self):
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            LeadScore(rubric_version="v1.0")  # type: ignore


class TestResearchFindings:
    """Tests for ResearchFindings model."""
    
    def test_valid_minimal(self):
        """Valid research findings with minimal fields."""
        findings = ResearchFindings(job_id="job123")
        assert findings.job_id == "job123"
        assert findings.company_snapshot == []
        assert findings.decision_makers == []
        assert findings.projects_signals == []

    def test_with_findings(self):
        """Valid research findings with populated finding lists."""
        finding = Finding(
            field="company_size",
            value="500",
            label=EvidenceLabel.VERIFIED
        )
        findings = ResearchFindings(
            job_id="job123",
            company_snapshot=[finding],
            decision_makers=[finding]
        )
        assert len(findings.company_snapshot) == 1
        assert len(findings.decision_makers) == 1

    def test_notes_missing_default(self):
        """Optional field: notes_missing defaults to empty list."""
        findings = ResearchFindings(job_id="job123")
        assert findings.notes_missing == []

    def test_notes_missing_with_values(self):
        """Optional field: notes_missing can have values."""
        findings = ResearchFindings(
            job_id="job123",
            notes_missing=["No revenue data found", "No recent hires listed"]
        )
        assert len(findings.notes_missing) == 2


class TestOutreachDrafts:
    """Tests for OutreachDrafts model — Req 6.1, 7.5 (status locked to draft)."""
    
    def test_status_always_draft(self):
        """Status validation: default status is 'draft'."""
        d = OutreachDrafts(job_id="abc")
        assert d.status == "draft"

    def test_status_explicitly_draft(self):
        """Status validation: explicit 'draft' accepted."""
        d = OutreachDrafts(job_id="abc", status="draft")
        assert d.status == "draft"

    def test_cannot_set_non_draft_status(self):
        """Status validation: non-draft status rejected."""
        with pytest.raises(ValidationError):
            OutreachDrafts(
                job_id="abc",
                status="sent",  # type: ignore
            )

    def test_cannot_set_sent_status(self):
        """Status validation: 'sent' status rejected."""
        with pytest.raises(ValidationError):
            OutreachDrafts(job_id="abc", status="sent")  # type: ignore

    def test_cannot_set_published_status(self):
        """Status validation: 'published' status rejected."""
        with pytest.raises(ValidationError):
            OutreachDrafts(job_id="abc", status="published")  # type: ignore

    def test_email_fields_empty_by_default(self):
        """Optional email fields default to empty strings."""
        d = OutreachDrafts(job_id="abc")
        assert d.email_subject == ""
        assert d.email_body == ""
        assert d.email_touch_1 == ""
        assert d.email_touch_2 == ""
        assert d.email_touch_3 == ""

    def test_linkedin_fields_empty_by_default(self):
        """Optional LinkedIn fields default to empty strings."""
        d = OutreachDrafts(job_id="abc")
        assert d.linkedin_message == ""
        assert d.linkedin_connection == ""
        assert d.linkedin_pitch == ""

    def test_review_note_default(self):
        """Optional field: review_note defaults to 'draft — requires human review before use'."""
        d = OutreachDrafts(job_id="abc")
        assert d.review_note == "draft \u2014 requires human review before use"

    def test_all_content_fields(self):
        """Valid outreach drafts with all content fields populated."""
        d = OutreachDrafts(
            job_id="job123",
            email_subject="Subject",
            email_body="Body",
            email_touch_1="Touch 1",
            email_touch_2="Touch 2",
            email_touch_3="Touch 3",
            linkedin_message="Message",
            linkedin_connection="Connect",
            linkedin_pitch="Pitch"
        )
        assert d.email_subject == "Subject"
        assert d.status == "draft"


class TestCRMExportRecord:
    """Tests for CRMExportRecord model — Req 4.1 (score range validation)."""
    
    def test_valid_record(self):
        """Valid CRM export record."""
        record = CRMExportRecord(
            job_id="job123",
            lead_score_total=75,
            lead_score_band="High"
        )
        assert record.lead_score_total == 75
        assert record.lead_score_band == "High"

    def test_score_range_valid(self):
        """Score total range: 0-100 accepted."""
        for score in [0, 50, 100]:
            record = CRMExportRecord(
                job_id="job123",
                lead_score_total=score,
                lead_score_band="High"
            )
            assert record.lead_score_total == score

    def test_score_out_of_range_high(self):
        """Score total range: rejects > 100."""
        with pytest.raises(ValidationError):
            CRMExportRecord(
                job_id="job123",
                lead_score_total=101,
                lead_score_band="High"
            )

    def test_score_out_of_range_low(self):
        """Score total range: rejects < 0."""
        with pytest.raises(ValidationError):
            CRMExportRecord(
                job_id="job123",
                lead_score_total=-1,
                lead_score_band="Low"
            )

    def test_optional_fields_default(self):
        """Optional fields default appropriately."""
        record = CRMExportRecord(
            job_id="job123",
            lead_score_total=50,
            lead_score_band="Medium"
        )
        assert record.company_fields == {}
        assert record.contact_fields == {}
        assert record.deal_fields == {}
        assert record.possible_duplicate is False

    def test_with_custom_fields(self):
        """CRM fields can be populated with custom data."""
        record = CRMExportRecord(
            job_id="job123",
            lead_score_total=75,
            lead_score_band="High",
            company_fields={"name": "Acme Corp", "size": "500-1000"},
            contact_fields={"name": "John Doe", "title": "CEO"}
        )
        assert record.company_fields["name"] == "Acme Corp"
        assert record.contact_fields["name"] == "John Doe"


class TestFeedbackCreate:
    """Tests for FeedbackCreate model."""
    
    def test_valid_feedback(self):
        """Valid feedback submission."""
        feedback = FeedbackCreate(
            score_accuracy="about_right",
            brief_quality="good",
            outreach_quality="good",
            comment="Excellent brief"
        )
        assert feedback.score_accuracy == "about_right"
        assert feedback.brief_quality == "good"

    def test_score_accuracy_values(self):
        """Enum constraint: score_accuracy only accepts specified values."""
        for value in ["too_low", "about_right", "too_high"]:
            feedback = FeedbackCreate(
                score_accuracy=value,  # type: ignore
                brief_quality="okay"
            )
            assert feedback.score_accuracy == value

    def test_brief_quality_values(self):
        """Enum constraint: brief_quality only accepts specified values."""
        for value in ["poor", "okay", "good"]:
            feedback = FeedbackCreate(
                score_accuracy="about_right",
                brief_quality=value  # type: ignore
            )
            assert feedback.brief_quality == value

    def test_outreach_quality_default(self):
        """Optional field: outreach_quality defaults to 'not_applicable'."""
        feedback = FeedbackCreate(
            score_accuracy="about_right",
            brief_quality="good"
        )
        assert feedback.outreach_quality == "not_applicable"

    def test_outreach_quality_values(self):
        """Enum constraint: outreach_quality accepts specified values."""
        for value in ["poor", "okay", "good", "not_applicable"]:
            feedback = FeedbackCreate(
                score_accuracy="about_right",
                brief_quality="good",
                outreach_quality=value  # type: ignore
            )
            assert feedback.outreach_quality == value

    def test_comment_max_length(self):
        """String constraint: comment max_length=2000."""
        long_comment = "A" * 2001
        with pytest.raises(ValidationError):
            FeedbackCreate(
                score_accuracy="about_right",
                brief_quality="good",
                comment=long_comment
            )

    def test_comment_max_length_valid(self):
        """String constraint: comment exactly at max length (2000) is valid."""
        long_comment = "A" * 2000
        feedback = FeedbackCreate(
            score_accuracy="about_right",
            brief_quality="good",
            comment=long_comment
        )
        assert len(feedback.comment) == 2000

    def test_submitted_by_max_length(self):
        """String constraint: submitted_by max_length=100."""
        long_name = "A" * 101
        with pytest.raises(ValidationError):
            FeedbackCreate(
                score_accuracy="about_right",
                brief_quality="good",
                submitted_by=long_name
            )

    def test_optional_fields(self):
        """Optional fields can be None."""
        feedback = FeedbackCreate(
            score_accuracy="about_right",
            brief_quality="good",
            comment=None,
            submitted_by=None
        )
        assert feedback.comment is None
        assert feedback.submitted_by is None


class TestRecommendedApproach:
    """Tests for RecommendedApproach model."""
    
    def test_valid_approach(self):
        """Valid recommended approach."""
        approach = RecommendedApproach(
            summary="Focus on operational efficiency",
            angle="Cost reduction",
            key_capabilities_to_lead_with=["Process Automation", "Cost Analysis"],
            knowledge_sources=["Case Study 1", "Case Study 2"]
        )
        assert approach.summary == "Focus on operational efficiency"
        assert len(approach.key_capabilities_to_lead_with) == 2

    def test_optional_angle(self):
        """Optional field: angle can be None."""
        approach = RecommendedApproach(summary="Test")
        assert approach.angle is None

    def test_default_lists(self):
        """Optional list fields default to empty lists."""
        approach = RecommendedApproach(summary="Test")
        assert approach.key_capabilities_to_lead_with == []
        assert approach.knowledge_sources == []


class TestNextAction:
    """Tests for NextAction model."""
    
    def test_valid_action(self):
        """Valid next action."""
        action = NextAction(
            action="Send personalized email",
            owner="Sales Team",
            notes="Reference operational efficiency in subject"
        )
        assert action.action == "Send personalized email"
        assert action.owner == "Sales Team"

    def test_optional_owner(self):
        """Optional field: owner can be None."""
        action = NextAction(action="Follow up")
        assert action.owner is None

    def test_optional_notes(self):
        """Optional field: notes can be None."""
        action = NextAction(action="Follow up", notes=None)
        assert action.notes is None


class TestKnowledgeCitation:
    """Tests for KnowledgeCitation model."""
    
    def test_valid_citation(self):
        """Valid knowledge citation."""
        citation = KnowledgeCitation(
            statement="We specialize in operational efficiency",
            source_document="case_studies.pdf",
            section="Operational Excellence"
        )
        assert citation.statement == "We specialize in operational efficiency"
        assert citation.source_document == "case_studies.pdf"

    def test_required_fields(self):
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            KnowledgeCitation(statement="Test")  # type: ignore

    def test_optional_section(self):
        """Optional field: section can be None."""
        citation = KnowledgeCitation(
            statement="Test statement",
            source_document="document.pdf",
            section=None
        )
        assert citation.section is None


class TestResearchBrief:
    """Tests for ResearchBrief model."""
    
    def test_valid_brief(self):
        """Valid research brief with required fields."""
        breakdown = [
            ScoreFactor(factor="test", weight=20, points_awarded=20, evidence="test")
        ]
        lead_score = LeadScore(
            rubric_version="v1.0",
            total=75,
            band="A / Strong fit",
            breakdown=breakdown
        )
        approach = RecommendedApproach(summary="Test approach")
        action = NextAction(action="Test action")
        
        brief = ResearchBrief(
            job_id="job123",
            lead_score=lead_score,
            recommended_approach=approach,
            next_action=action
        )
        assert brief.job_id == "job123"
        assert brief.lead_score.total == 75

    def test_optional_dict_fields_default(self):
        """Optional dict fields default to empty dicts."""
        breakdown = [ScoreFactor(factor="test", weight=20, points_awarded=20, evidence="test")]
        lead_score = LeadScore(rubric_version="v1.0", total=50, band="B / Nurture", breakdown=breakdown)
        approach = RecommendedApproach(summary="Test")
        action = NextAction(action="Test")
        
        brief = ResearchBrief(
            job_id="job123",
            lead_score=lead_score,
            recommended_approach=approach,
            next_action=action
        )
        assert brief.snapshot == {}
        assert brief.contact == {}
        assert brief.company_research == {}

    def test_optional_list_fields_default(self):
        """Optional list fields default to empty lists."""
        breakdown = [ScoreFactor(factor="test", weight=20, points_awarded=20, evidence="test")]
        lead_score = LeadScore(rubric_version="v1.0", total=50, band="B / Nurture", breakdown=breakdown)
        approach = RecommendedApproach(summary="Test")
        action = NextAction(action="Test")
        
        brief = ResearchBrief(
            job_id="job123",
            lead_score=lead_score,
            recommended_approach=approach,
            next_action=action
        )
        assert brief.projects_signals == []
        assert brief.likely_requirements == []
        assert brief.pain_point_hypotheses == []
        assert brief.risks_unknowns == []
        assert brief.sources == []
        assert brief.knowledge_citations == []

    def test_validation_skipped_default(self):
        """Optional field: validation_skipped defaults to False."""
        breakdown = [ScoreFactor(factor="test", weight=20, points_awarded=20, evidence="test")]
        lead_score = LeadScore(rubric_version="v1.0", total=50, band="B / Nurture", breakdown=breakdown)
        approach = RecommendedApproach(summary="Test")
        action = NextAction(action="Test")
        
        brief = ResearchBrief(
            job_id="job123",
            lead_score=lead_score,
            recommended_approach=approach,
            next_action=action
        )
        assert brief.validation_skipped is False


class TestProposalDraft:
    """Tests for ProposalDraft model."""
    
    def test_valid_proposal(self):
        """Valid proposal draft."""
        proposal = ProposalDraft(
            job_id="job123",
            proposal_title="Operational Efficiency Program",
            client_requirement="Reduce operating costs",
            turnaround_programme="8 weeks",
            pilot_option="Pilot Phase 1",
            rendered_markdown="# Proposal"
        )
        assert proposal.job_id == "job123"
        assert proposal.status == "draft"

    def test_status_always_draft(self):
        """Status validation: always 'draft'."""
        proposal = ProposalDraft(
            job_id="job123",
            proposal_title="Test",
            client_requirement="Test",
            turnaround_programme="4 weeks",
            pilot_option="Pilot",
            rendered_markdown="Test"
        )
        assert proposal.status == "draft"

    def test_cannot_set_non_draft_status(self):
        """Status validation: non-draft status rejected."""
        with pytest.raises(ValidationError):
            ProposalDraft(
                job_id="job123",
                proposal_title="Test",
                client_requirement="Test",
                turnaround_programme="4 weeks",
                pilot_option="Pilot",
                rendered_markdown="Test",
                status="sent"  # type: ignore
            )

    def test_optional_lists_default(self):
        """Optional list fields default to empty lists."""
        proposal = ProposalDraft(
            job_id="job123",
            proposal_title="Test",
            client_requirement="Test",
            turnaround_programme="4 weeks",
            pilot_option="Pilot",
            rendered_markdown="Test"
        )
        assert proposal.proposed_scope == []
        assert proposal.deliverables == []
        assert proposal.commercial_options == []
        assert proposal.assumptions_exclusions == []

    def test_required_fields(self):
        """Required fields must be provided."""
        with pytest.raises(ValidationError):
            ProposalDraft(
                job_id="job123",
                proposal_title="Test",
                client_requirement="Test",
                turnaround_programme="4 weeks",
                rendered_markdown="Test"
                # Missing pilot_option
            )

    def test_with_all_fields(self):
        """Proposal with all fields populated."""
        proposal = ProposalDraft(
            job_id="job123",
            proposal_title="Test",
            client_requirement="Test",
            proposed_scope=["Scope 1"],
            deliverables=["Deliverable 1"],
            turnaround_programme="4 weeks",
            commercial_options=[{"option": "Standard"}],
            assumptions_exclusions=["Assumption 1"],
            pilot_option="Pilot",
            rendered_markdown="Test"
        )
        assert len(proposal.proposed_scope) == 1
        assert len(proposal.deliverables) == 1
