"""
Task 7.5 / Requirement 8.4 — Anti-fabrication tests.
Asserts that when input is deliberately incomplete/ambiguous,
the system reports missing information rather than inventing it.
"""
import pytest

from api.models import EvidenceLabel, Finding, ResearchFindings
from scoring.engine import score


class TestMissingEvidenceHandling:
    def test_empty_findings_notes_missing_not_crash(self):
        """Empty findings produce a valid score with all-zero breakdown."""
        findings = ResearchFindings(job_id="empty")
        lead_score = score(findings)
        # Every factor must have 0 points — never a positive score from nothing
        for factor in lead_score.breakdown:
            assert factor.points_awarded == 0, (
                f"Factor '{factor.factor}' awarded {factor.points_awarded} points "
                f"with no evidence — should be 0."
            )

    def test_no_evidence_value_scores_zero(self):
        """A finding with value 'no evidence found' must never award positive points."""
        findings = ResearchFindings(
            job_id="no-evidence",
            company_snapshot=[
                Finding(
                    field=field,
                    value="no evidence found",
                    label=EvidenceLabel.UNVERIFIED,
                )
                for field in [
                    "trade_fit", "geography", "company_size_band",
                    "tender_volume_signal", "estimating_need_signal",
                    "drafting_bim_need_signal", "hiring_trigger",
                    "decision_maker_access", "outsourcing_readiness",
                    "commercial_attractiveness",
                ]
            ],
        )
        lead_score = score(findings)
        assert lead_score.total == 0
        assert lead_score.band == "D / Disqualify"

    def test_unverified_label_does_not_upgrade(self):
        """
        A finding labelled Unverified must remain Unverified after passing
        through the scoring engine (scoring engine should not alter labels).
        """
        findings = ResearchFindings(
            job_id="label-check",
            company_snapshot=[
                Finding(
                    field="trade_fit",
                    value="facade contractor",
                    label=EvidenceLabel.UNVERIFIED,
                )
            ],
        )
        # Scoring reads the value but must not touch the label
        lead_score = score(findings)
        original_label = findings.company_snapshot[0].label
        assert original_label == EvidenceLabel.UNVERIFIED, "Label was mutated by scoring engine"

    def test_ambiguous_company_size_scores_conservatively(self):
        """Ambiguous size description does not award full points."""
        findings = ResearchFindings(
            job_id="ambiguous-size",
            company_snapshot=[
                Finding(
                    field="company_size_band",
                    value="medium-sized company",  # no number — ambiguous
                    label=EvidenceLabel.PROBABLE,
                )
            ],
        )
        lead_score = score(findings)
        size_factor = next(
            f for f in lead_score.breakdown if f.factor == "company_size_capacity"
        )
        # No number found → 0 points (conservative)
        assert size_factor.points_awarded == 0

    def test_partial_information_leaves_other_factors_at_zero(self):
        """Only trade_fit provided; all other factors should score 0."""
        findings = ResearchFindings(
            job_id="partial",
            company_snapshot=[
                Finding(
                    field="trade_fit",
                    value="facade contractor",
                    label=EvidenceLabel.VERIFIED,
                )
            ],
        )
        lead_score = score(findings)
        for factor in lead_score.breakdown:
            if factor.factor == "trade_service_fit":
                assert factor.points_awarded == 20
            else:
                assert factor.points_awarded == 0, (
                    f"Factor '{factor.factor}' should be 0 without evidence, got {factor.points_awarded}"
                )
