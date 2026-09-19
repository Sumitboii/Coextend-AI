"""
Deterministic Lead Scoring Engine.

score(findings) -> LeadScore

Pure function — no LLM, no I/O, no randomness.
Same findings always produce the same score (repeatable).
"""
from __future__ import annotations

from api.models import Finding, LeadScore, ResearchFindings, ScoreFactor
from scoring.rubric import RUBRIC_FACTORS, RUBRIC_VERSION, assign_band


def _get_finding_value(findings: ResearchFindings, field_name: str) -> str:
    """
    Look up the value of a specific field across all finding sections.
    Returns "no evidence found" if not present, ensuring 0-point default.
    """
    all_findings: list[Finding] = (
        findings.company_snapshot
        + findings.decision_makers
        + findings.projects_signals
    )
    for f in all_findings:
        if f.field == field_name:
            return f.value
    return "no evidence found"


def score(findings: ResearchFindings) -> LeadScore:
    """
    Compute a deterministic 0–100 lead score from structured findings.

    Steps:
    1. For each rubric factor, read the corresponding finding field value.
    2. Apply the banded score function → points awarded (capped at weight).
    3. Sum all points.
    4. Assign a priority band.
    5. Collect zero_evidence_factors: factors whose field was entirely absent.
    6. Return LeadScore with full breakdown.
    """
    breakdown: list[ScoreFactor] = []
    zero_evidence_factors: list[str] = []
    total = 0

    # Build a set of all field names present across the three finding lists
    # so we can distinguish "field present but scored 0" from "field absent entirely".
    all_findings: list = (
        findings.company_snapshot
        + findings.decision_makers
        + findings.projects_signals
    )
    present_fields = {f.field for f in all_findings}

    for factor in RUBRIC_FACTORS:
        value = _get_finding_value(findings, factor.finding_field)
        points = factor.score_fn(value)
        # Cap at weight (should not happen with correct rules, but safety net)
        points = min(points, factor.weight)
        # Ensure non-negative
        points = max(points, 0)

        # Track factors that scored 0 because their field was entirely absent (Req 4.5)
        if factor.finding_field not in present_fields:
            zero_evidence_factors.append(factor.name)

        breakdown.append(
            ScoreFactor(
                factor=factor.name,
                weight=factor.weight,
                points_awarded=points,
                evidence=f"[{factor.finding_field}] = {value!r}",
            )
        )
        total += points

    total = min(total, 100)
    band = assign_band(total)

    return LeadScore(
        rubric_version=RUBRIC_VERSION,
        total=total,
        band=band,
        breakdown=breakdown,
        zero_evidence_factors=zero_evidence_factors,
    )
