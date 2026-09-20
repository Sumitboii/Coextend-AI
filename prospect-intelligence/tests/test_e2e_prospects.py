"""
Task 11.5 / Requirement 10.4 — End-to-end scoring tests for 5 prospect
archetypes (no live API calls — uses mocked findings).

This exercises the full scoring + scoring-repeatability requirements
(Req 4.4) against realistic prospect profiles.
"""
import pytest

from api.models import EvidenceLabel, Finding, ResearchFindings
from scoring.engine import score
from scoring.rubric import RUBRIC_VERSION


def _findings(job_id: str, fields: dict) -> ResearchFindings:
    return ResearchFindings(
        job_id=job_id,
        company_snapshot=[
            Finding(field=k, value=v, label=EvidenceLabel.VERIFIED)
            for k, v in fields.items()
        ],
    )


# 5 test prospects

# Prospect 1 — Clear High-fit (UK facade contractor, strong signals)
PROSPECT_1 = _findings("p1-high-fit", {
    "trade_fit": "facade cladding contractor",
    "geography": "UK",
    "company_size_band": "200 employees",
    "tender_volume_signal": "multiple active tenders on framework",
    "estimating_need_signal": "QS take-off estimating",
    "drafting_bim_need_signal": "BIM shop drawings Revit",
    "hiring_trigger": "hiring BIM coordinator estimator",
    "decision_maker_access": "Commercial Director identified",
    "outsourcing_readiness": "outsourced drafting previously",
    "commercial_attractiveness": "£40m turnover award winning",
})

# Prospect 2 — Clear Poor-fit (software company, wrong geography)
PROSPECT_2 = _findings("p2-poor-fit", {
    "trade_fit": "software development company",
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

# Prospect 3 — Ambiguous (some signals, incomplete info)
PROSPECT_3 = _findings("p3-ambiguous", {
    "trade_fit": "general contractor",
    "geography": "Canada",
    "company_size_band": "no evidence found",
    "tender_volume_signal": "bid for a project",
    "estimating_need_signal": "growing pipeline",
    "drafting_bim_need_signal": "no evidence found",
    "hiring_trigger": "no evidence found",
    "decision_maker_access": "Director mentioned",
    "outsourcing_readiness": "no evidence found",
    "commercial_attractiveness": "secured major contract",
})

# Prospect 4 — Ambiguous (facade but small/unknown size, no DM access)
PROSPECT_4 = _findings("p4-partial", {
    "trade_fit": "curtain wall glazing specialist",
    "geography": "US",
    "company_size_band": "medium company",   # ambiguous — no number
    "tender_volume_signal": "active tender pipeline",
    "estimating_need_signal": "no evidence found",
    "drafting_bim_need_signal": "technical design team",
    "hiring_trigger": "several vacancies",
    "decision_maker_access": "no evidence found",
    "outsourcing_readiness": "capacity stretched",
    "commercial_attractiveness": "no evidence found",
})

# Prospect 5 — Australia expansion target (medium fit)
PROSPECT_5 = _findings("p5-expansion", {
    "trade_fit": "roofing contractor",
    "geography": "Australia",
    "company_size_band": "80 employees",
    "tender_volume_signal": "active tendering",
    "estimating_need_signal": "estimating department small",
    "drafting_bim_need_signal": "no evidence found",
    "hiring_trigger": "general hiring",
    "decision_maker_access": "Managing Director identified",
    "outsourcing_readiness": "growing team capacity",
    "commercial_attractiveness": "no evidence found",
})


class TestEndToEndProspects:
    def test_p1_high_fit_scores_above_70(self):
        s = score(PROSPECT_1)
        assert s.total >= 80, f"P1 high-fit expected ≥80, got {s.total}"
        assert s.band == "A+ / Priority"

    def test_p2_poor_fit_scores_below_15(self):
        s = score(PROSPECT_2)
        assert s.total <= 15, f"P2 poor-fit expected ≤15, got {s.total}"
        assert s.band == "D / Disqualify"

    def test_p3_ambiguous_scores_medium_range(self):
        s = score(PROSPECT_3)
        assert 15 <= s.total <= 60, f"P3 ambiguous expected 15-60, got {s.total}"

    def test_p4_partial_does_not_invent_points(self):
        s = score(PROSPECT_4)
        # company_size_band is ambiguous string — should score 0 for that factor
        size_factor = next(f for f in s.breakdown if f.factor == "company_size_capacity")
        assert size_factor.points_awarded == 0

    def test_p5_expansion_scores_medium(self):
        s = score(PROSPECT_5)
        # Australia gives half geography points; roofing gives max trade fit
        # Expect moderate score
        assert s.total > 0
        geo_factor = next(f for f in s.breakdown if f.factor == "geography")
        assert geo_factor.points_awarded == 5  # expansion market

    def test_all_have_ten_factors(self):
        for p in [PROSPECT_1, PROSPECT_2, PROSPECT_3, PROSPECT_4, PROSPECT_5]:
            s = score(p)
            assert len(s.breakdown) == 10

    def test_rubric_version_consistent(self):
        for p in [PROSPECT_1, PROSPECT_2, PROSPECT_3, PROSPECT_4, PROSPECT_5]:
            s = score(p)
            assert s.rubric_version == RUBRIC_VERSION

    def test_score_repeatability_all_prospects(self):
        """Req 4.4 — each prospect scored twice gives identical results."""
        for p in [PROSPECT_1, PROSPECT_2, PROSPECT_3, PROSPECT_4, PROSPECT_5]:
            s1 = score(p)
            s2 = score(p)
            assert s1.total == s2.total, f"Score not repeatable for {p.job_id}"
            assert s1.band == s2.band
            for f1, f2 in zip(s1.breakdown, s2.breakdown):
                assert f1.points_awarded == f2.points_awarded, (
                    f"Factor {f1.factor} not repeatable for {p.job_id}"
                )
