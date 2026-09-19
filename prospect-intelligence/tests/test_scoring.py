"""
Task 6 — Deterministic lead scoring engine tests.
Tests each factor independently, including the 0-points / no-evidence path.
Also contains the score-repeatability test (Req. 4.4).
"""
import pytest

from api.models import EvidenceLabel, Finding, ResearchFindings
from scoring.engine import score
from scoring.rubric import (
    RUBRIC_VERSION,
    assign_band,
    _trade_fit_score,
    _geography_score,
    _company_size_score,
    _tender_volume_score,
    _estimating_need_score,
    _drafting_bim_score,
    _hiring_trigger_score,
    _decision_maker_score,
    _outsourcing_readiness_score,
    _commercial_attractiveness_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_findings(fields: dict, job_id: str = "test-job") -> ResearchFindings:
    """Build a minimal ResearchFindings with specific field values."""
    snapshot = [
        Finding(field=k, value=v, label=EvidenceLabel.VERIFIED)
        for k, v in fields.items()
    ]
    return ResearchFindings(job_id=job_id, company_snapshot=snapshot)


# ---------------------------------------------------------------------------
# Trade / service fit
# ---------------------------------------------------------------------------

class TestTradeFit:
    def test_facade_scores_max(self):
        assert _trade_fit_score("facade contractor") == 20

    def test_cladding_scores_max(self):
        assert _trade_fit_score("cladding specialist") == 20

    def test_roofing_scores_max(self):
        assert _trade_fit_score("commercial roofing") == 20

    def test_curtain_wall_scores_15(self):
        assert _trade_fit_score("curtain wall installation") == 15

    def test_general_contractor_scores_5(self):
        assert _trade_fit_score("general contractor") == 5

    def test_no_evidence_scores_0(self):
        assert _trade_fit_score("no evidence found") == 0

    def test_unrelated_scores_0(self):
        assert _trade_fit_score("software company") == 0


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

class TestGeography:
    def test_uk_scores_10(self):
        assert _geography_score("UK") == 10

    def test_united_kingdom_scores_10(self):
        assert _geography_score("United Kingdom, England") == 10

    def test_us_scores_10(self):
        assert _geography_score("US, United States") == 10

    def test_canada_scores_10(self):
        assert _geography_score("Canada") == 10

    def test_australia_scores_5(self):
        assert _geography_score("Australia") == 5

    def test_uae_scores_5(self):
        assert _geography_score("UAE") == 5

    def test_unknown_scores_0(self):
        assert _geography_score("no evidence found") == 0

    def test_germany_scores_0(self):
        assert _geography_score("Germany") == 0


# ---------------------------------------------------------------------------
# Company size
# ---------------------------------------------------------------------------

class TestCompanySize:
    def test_200_employees_scores_10(self):
        assert _company_size_score("200 employees") == 10

    def test_50_employees_scores_10(self):
        assert _company_size_score("50 employees") == 10

    def test_500_employees_scores_10(self):
        assert _company_size_score("500 employees") == 10

    def test_30_employees_scores_5(self):
        assert _company_size_score("30 employees") == 5

    def test_1000_employees_scores_3(self):
        assert _company_size_score("1000 employees") == 3

    def test_no_evidence_scores_0(self):
        assert _company_size_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Tender volume
# ---------------------------------------------------------------------------

class TestTenderVolume:
    def test_multiple_tenders_scores_15(self):
        assert _tender_volume_score("multiple active tenders") == 15

    def test_framework_scores_15(self):
        assert _tender_volume_score("on multiple frameworks") == 15

    def test_some_tender_evidence_scores_8(self):
        assert _tender_volume_score("bid for contract") == 8

    def test_no_evidence_scores_0(self):
        assert _tender_volume_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Estimating need
# ---------------------------------------------------------------------------

class TestEstimatingNeed:
    def test_estimating_scores_10(self):
        assert _estimating_need_score("in-house estimating team") == 10

    def test_takeoff_scores_10(self):
        assert _estimating_need_score("take-off required") == 10

    def test_boq_scores_10(self):
        assert _estimating_need_score("BOQ preparation") == 10

    def test_growing_implies_need(self):
        assert _estimating_need_score("growing pipeline") == 5

    def test_no_evidence_scores_0(self):
        assert _estimating_need_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Drafting / BIM
# ---------------------------------------------------------------------------

class TestDraftingBIM:
    def test_bim_scores_10(self):
        assert _drafting_bim_score("BIM coordination") == 10

    def test_shop_drawings_scores_10(self):
        assert _drafting_bim_score("shop drawing production") == 10

    def test_revit_scores_10(self):
        assert _drafting_bim_score("Revit models") == 10

    def test_design_implies_need(self):
        assert _drafting_bim_score("design team") == 5

    def test_no_evidence_scores_0(self):
        assert _drafting_bim_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Hiring trigger
# ---------------------------------------------------------------------------

class TestHiringTrigger:
    def test_bim_hiring_scores_10(self):
        assert _hiring_trigger_score("hiring BIM coordinator") == 10

    def test_estimating_hiring_scores_10(self):
        assert _hiring_trigger_score("Estimator vacancy") == 10

    def test_general_hiring_scores_5(self):
        assert _hiring_trigger_score("growing team, several vacancies") == 5

    def test_no_evidence_scores_0(self):
        assert _hiring_trigger_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Decision maker access
# ---------------------------------------------------------------------------

class TestDecisionMakerAccess:
    def test_managing_director_scores_5(self):
        assert _decision_maker_score("Managing Director identified") == 5

    def test_commercial_director_scores_5(self):
        assert _decision_maker_score("Commercial Director") == 5

    def test_generic_director_scores_2(self):
        assert _decision_maker_score("Director of Operations") == 2

    def test_no_evidence_scores_0(self):
        assert _decision_maker_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Outsourcing readiness
# ---------------------------------------------------------------------------

class TestOutsourcingReadiness:
    def test_outsourcing_evidence_scores_5(self):
        assert _outsourcing_readiness_score("outsourced drafting previously") == 5

    def test_capacity_scores_2(self):
        assert _outsourcing_readiness_score("capacity stretched due to growth") == 2

    def test_no_evidence_scores_0(self):
        assert _outsourcing_readiness_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Commercial attractiveness
# ---------------------------------------------------------------------------

class TestCommercialAttractiveness:
    def test_million_scores_5(self):
        assert _commercial_attractiveness_score("£50m turnover") == 5

    def test_award_scores_5(self):
        assert _commercial_attractiveness_score("award-winning tier 1 contractor") == 5

    def test_contract_mention_scores_2(self):
        assert _commercial_attractiveness_score("secured major contract") == 2

    def test_no_evidence_scores_0(self):
        assert _commercial_attractiveness_score("no evidence found") == 0


# ---------------------------------------------------------------------------
# Band assignment (5-tier ICP classification)
# ---------------------------------------------------------------------------

class TestBandAssignment:
    def test_a_plus_band(self):
        assert assign_band(80) == "A+ / Priority"
        assert assign_band(100) == "A+ / Priority"

    def test_a_band(self):
        assert assign_band(65) == "A / Strong fit"
        assert assign_band(79) == "A / Strong fit"

    def test_b_band(self):
        assert assign_band(50) == "B / Nurture"
        assert assign_band(64) == "B / Nurture"

    def test_c_band(self):
        assert assign_band(35) == "C / Low priority"
        assert assign_band(49) == "C / Low priority"

    def test_d_band(self):
        assert assign_band(0) == "D / Disqualify"
        assert assign_band(34) == "D / Disqualify"


# ---------------------------------------------------------------------------
# Full score function
# ---------------------------------------------------------------------------

class TestScoreFunction:
    def test_strong_prospect_scores_high(self):
        findings = make_findings({
            "trade_fit": "facade cladding contractor",
            "geography": "UK",
            "company_size_band": "150 employees",
            "tender_volume_signal": "multiple active tenders on framework",
            "estimating_need_signal": "in-house estimating take-off",
            "drafting_bim_need_signal": "BIM coordination shop drawings",
            "hiring_trigger": "hiring BIM coordinator estimator",
            "decision_maker_access": "Commercial Director identified",
            "outsourcing_readiness": "outsourced drafting previously",
            "commercial_attractiveness": "£30m turnover award-winning",
        })
        lead_score = score(findings)
        assert lead_score.total >= 80
        assert lead_score.band == "A+ / Priority"
        assert lead_score.rubric_version == RUBRIC_VERSION

    def test_poor_fit_scores_low(self):
        findings = make_findings({
            "trade_fit": "software company",
            "geography": "Germany",
            "company_size_band": "no evidence found",
            "tender_volume_signal": "no evidence found",
            "estimating_need_signal": "no evidence found",
            "drafting_bim_need_signal": "no evidence found",
            "hiring_trigger": "no evidence found",
            "decision_maker_access": "no evidence found",
            "outsourcing_readiness": "no evidence found",
            "commercial_attractiveness": "no evidence found",
        })
        lead_score = score(findings)
        assert lead_score.total <= 10
        assert lead_score.band == "D / Disqualify"

    def test_missing_fields_score_zero_not_crash(self):
        """No scoring fields present — all default to 0 points (no crash)."""
        findings = ResearchFindings(job_id="empty-job")
        lead_score = score(findings)
        assert lead_score.total == 0
        assert lead_score.band == "D / Disqualify"

    def test_score_repeatability(self):
        """Req 4.4 — same findings scored twice must return identical results."""
        findings = make_findings({
            "trade_fit": "cladding contractor",
            "geography": "Canada",
            "company_size_band": "75 employees",
            "tender_volume_signal": "active tender pipeline",
            "estimating_need_signal": "QS take-off needed",
        }, job_id="repeat-test")

        score_a = score(findings)
        score_b = score(findings)

        assert score_a.total == score_b.total
        assert score_a.band == score_b.band
        assert score_a.rubric_version == score_b.rubric_version
        for fa, fb in zip(score_a.breakdown, score_b.breakdown):
            assert fa.factor == fb.factor
            assert fa.points_awarded == fb.points_awarded

    def test_breakdown_has_ten_factors(self):
        findings = ResearchFindings(job_id="ten-factor")
        lead_score = score(findings)
        assert len(lead_score.breakdown) == 10

    def test_total_never_exceeds_100(self):
        findings = make_findings({
            "trade_fit": "facade cladding contractor",
            "geography": "UK",
            "company_size_band": "100 employees",
            "tender_volume_signal": "multiple active frameworks",
            "estimating_need_signal": "estimating takeoff required",
            "drafting_bim_need_signal": "BIM shop drawings",
            "hiring_trigger": "hiring BIM estimator",
            "decision_maker_access": "Managing Director",
            "outsourcing_readiness": "outsourced previously",
            "commercial_attractiveness": "£50m turnover award",
        })
        lead_score = score(findings)
        assert lead_score.total <= 100

# ---------------------------------------------------------------------------
# zero_evidence_factors tracking (Req 4.5, 4.7)
# ---------------------------------------------------------------------------

class TestZeroEvidenceFactors:
    def test_all_factors_in_zero_evidence_when_empty(self):
        """Req 4.7 — empty findings means all 10 factors are in zero_evidence_factors."""
        findings = ResearchFindings(job_id="empty-zef")
        lead_score = score(findings)
        assert lead_score.total == 0
        assert len(lead_score.zero_evidence_factors) == 10

    def test_present_field_not_in_zero_evidence(self):
        """A factor whose field IS present should NOT appear in zero_evidence_factors."""
        findings = make_findings({"trade_fit": "facade contractor"})
        lead_score = score(findings)
        assert "trade_service_fit" not in lead_score.zero_evidence_factors

    def test_absent_fields_appear_in_zero_evidence(self):
        """Factors for fields not present at all should be in zero_evidence_factors."""
        findings = make_findings({"trade_fit": "facade contractor"})
        lead_score = score(findings)
        # 9 factors have no corresponding field in findings
        assert len(lead_score.zero_evidence_factors) == 9

    def test_no_evidence_value_still_tracks_field_as_present(self):
        """
        A field set to 'no evidence found' is still present in findings, so it
        should NOT appear in zero_evidence_factors (it just scores 0).
        """
        findings = make_findings({
            "trade_fit": "no evidence found",
            "geography": "no evidence found",
        })
        lead_score = score(findings)
        assert "trade_service_fit" not in lead_score.zero_evidence_factors
        assert "geography" not in lead_score.zero_evidence_factors

    def test_all_fields_present_zero_evidence_empty(self):
        """When all 10 scoring fields are present, zero_evidence_factors is empty."""
        findings = make_findings({
            "trade_fit": "facade contractor",
            "geography": "UK",
            "company_size_band": "150 employees",
            "tender_volume_signal": "multiple tenders",
            "estimating_need_signal": "estimating need",
            "drafting_bim_need_signal": "BIM required",
            "hiring_trigger": "hiring estimator",
            "decision_maker_access": "Managing Director",
            "outsourcing_readiness": "outsourced before",
            "commercial_attractiveness": "£30m turnover",
        })
        lead_score = score(findings)
        assert lead_score.zero_evidence_factors == []
