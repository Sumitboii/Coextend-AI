"""
Scoring rubric configuration — single source of truth.
When thresholds or weights change, bump RUBRIC_VERSION.
Past scores remain attributable to the version that produced them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------
# Rubric version — bump this whenever scoring logic changes
# ---------------------------------------------------------------------------
RUBRIC_VERSION = "v1.0"

# ---------------------------------------------------------------------------
# Priority band thresholds (5-tier system from ICP document)
# ---------------------------------------------------------------------------
BAND_A_PLUS = "A+ / Priority"
BAND_A = "A / Strong fit"
BAND_B = "B / Nurture"
BAND_C = "C / Low priority"
BAND_D = "D / Disqualify"

TIER_RECOMMENDED_ACTIONS = {
    BAND_A_PLUS: "Personalised founder/director outreach; add to immediate call list; research trigger before message",
    BAND_A: "Targeted outreach sequence; offer relevant pilot or capacity conversation",
    BAND_B: "Automated sequence; monitor triggers and revisit when hiring/tender workload appears",
    BAND_C: "Light nurture only; do not spend high-touch sales time",
    BAND_D: "Exclude or suppress unless new evidence changes the score",
}


def assign_band(total: int) -> str:
    """
    Assign priority band based on the 5-tier ICP classification:
    80-100: "A+ / Priority"
    65-79:  "A / Strong fit"
    50-64:  "B / Nurture"
    35-49:  "C / Low priority"
    0-34:   "D / Disqualify"
    """
    if total >= 80:
        return BAND_A_PLUS
    if total >= 65:
        return BAND_A
    if total >= 50:
        return BAND_B
    if total >= 35:
        return BAND_C
    return BAND_D


def get_tier_action(band: str) -> str:
    """Get the recommended action for a given score classification tier."""
    return TIER_RECOMMENDED_ACTIONS.get(band, "")


# ---------------------------------------------------------------------------
# Factor definitions
# ---------------------------------------------------------------------------

@dataclass
class RubricFactor:
    name: str
    weight: int                        # max points for this factor
    score_fn: Callable[[str], int]     # (finding_value) -> points awarded
    finding_field: str                 # field name to read from ResearchFindings


def _trade_fit_score(value: str) -> int:
    """
    20 pts — strongest fit: facade / cladding / roofing contractor
    10 pts — adjacent: curtain wall, glazing, building envelope, exterior
     5 pts — possible: general contractor with specialist sub trades
     0 pts — no evidence or poor fit
    """
    v = value.lower()
    if any(k in v for k in ["facade", "cladding", "roofing", "façade"]):
        return 20
    if any(k in v for k in ["curtain wall", "glazing", "envelope", "exterior cladding"]):
        return 15
    if any(k in v for k in ["building envelope", "exterior", "aluminium", "steel framing"]):
        return 10
    if any(k in v for k in ["general contractor", "construction", "contractor"]):
        return 5
    return 0


def _geography_score(value: str) -> int:
    """
    10 pts — Primary markets: UK, US, Canada  
     5 pts — Approved expansion: Australia, Ireland, UAE, Singapore, New Zealand
     0 pts — All other markets / No evidence
    """
    v = value.lower()
    
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    
    # PRIMARY (10 pts) - UK, US, Canada
    primary = ["uk", "united kingdom", "england", "scotland", "wales", 
               "usa", "united states", "america", "canada"]
    if any(p in v for p in primary):
        return 10
    
    # Word boundary check for 'us' to avoid matching 'australia', 'plus', etc.
    import re
    if re.search(r"\bus\b", v):
        return 10
    
    # APPROVED EXPANSION (5 pts)
    approved = ["australia", "ireland", "uae", "united arab emirates", "singapore", "new zealand"]
    if any(a in v for a in approved):
        return 5
    
    # Country code shortcuts
    if re.search(r"\b(uk|us|ca)\b", v):  # UK, US, Canada codes
        return 10
    if re.search(r"\b(au|ie|ae|sg|nz)\b", v):  # Australia, Ireland, UAE, Singapore, New Zealand
        return 5
    
    return 0


def _company_size_score(value: str) -> int:
    """
    10 pts — 50–500 employees or £5m–£100m revenue (ideal for outsourcing)
     5 pts — 10–49 employees or <£5m revenue (possible early-stage)
     3 pts — 500+ employees (larger, slower sales cycle but worthwhile)
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    # Extract first number mentioned
    import re
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", v)]
    if not nums:
        return 0
    n = nums[0]
    if 50 <= n <= 500:
        return 10
    if 10 <= n < 50:
        return 5
    if n > 500:
        return 3
    return 0


def _tender_volume_score(value: str) -> int:
    """
    15 pts — clear evidence of active tendering (multiple tenders, frameworks)
     8 pts — some tender / project evidence
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    if any(k in v for k in ["multiple", "framework", "active", "high volume", "several"]):
        return 15
    if any(k in v for k in ["tender", "bid", "project", "pipeline"]):
        return 8
    return 0


def _estimating_need_score(value: str) -> int:
    """
    10 pts — explicit estimating / take-off / QS need or vacancy
     5 pts — implied (growing pipeline, no estimating staff mentioned)
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    if any(k in v for k in ["estimat", "take-off", "takeoff", "qs", "quantity survey", "bq", "boq"]):
        return 10
    if any(k in v for k in ["growing", "expansion", "recruit"]):
        return 5
    return 0


def _drafting_bim_score(value: str) -> int:
    """
    10 pts — explicit drafting / BIM / shop drawing need or role
     5 pts — implied (BIM mentioned but no dedicated resource)
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    if any(k in v for k in ["shop drawing", "bim", "drafting", "revit", "autocad", "tekla"]):
        return 10
    if any(k in v for k in ["design", "technical", "engineering"]):
        return 5
    return 0


def _hiring_trigger_score(value: str) -> int:
    """
    10 pts — active hiring in estimating / drafting / BIM roles
     5 pts — general hiring / growth signals
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    if any(k in v for k in ["estimat", "bim", "drafting", "shop draw", "take-off"]):
        return 10
    if any(k in v for k in ["hiring", "recruit", "vacancy", "job", "growing team"]):
        return 5
    return 0


def _decision_maker_score(value: str) -> int:
    """
    5 pts — named decision-maker identified (MD, Commercial Director, etc.)
     2 pts — probable decision-maker inferred from title / LinkedIn
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown", "not found"]):
        return 0
    if any(k in v for k in ["managing director", "commercial director", "estimating director",
                              "pre-construction", "technical director", "procurement", "qs director"]):
        return 5
    if any(k in v for k in ["director", "manager", "head of"]):
        return 2
    return 0


def _outsourcing_readiness_score(value: str) -> int:
    """
    5 pts — evidence of prior outsourcing or stated openness
     2 pts — implied openness (capacity stretch, project volume)
     0 pts — no evidence
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    if any(k in v for k in ["outsourc", "subcontract", "offshore", "external resource"]):
        return 5
    if any(k in v for k in ["capaci", "stretch", "busy", "growing"]):
        return 2
    return 0


def _commercial_attractiveness_score(value: str) -> int:
    """
    5 pts — high-value contracts, prestigious clients, strong financials
     2 pts — average commercial profile
     0 pts — no evidence or low value
    """
    v = value.lower()
    if any(k in v for k in ["no evidence", "unknown"]):
        return 0
    if any(k in v for k in ["£", "$", "million", "m turnover", "award", "prestige", "tier 1"]):
        return 5
    if any(k in v for k in ["contract", "revenue", "commercial"]):
        return 2
    return 0


# ---------------------------------------------------------------------------
# Ordered rubric factors
# ---------------------------------------------------------------------------

RUBRIC_FACTORS: list[RubricFactor] = [
    RubricFactor("trade_service_fit",       20, _trade_fit_score,           "trade_fit"),
    RubricFactor("geography",               10, _geography_score,           "geography"),
    RubricFactor("company_size_capacity",   10, _company_size_score,        "company_size_band"),
    RubricFactor("tender_project_volume",   15, _tender_volume_score,       "tender_volume_signal"),
    RubricFactor("estimating_need",         10, _estimating_need_score,     "estimating_need_signal"),
    RubricFactor("drafting_bim_need",       10, _drafting_bim_score,        "drafting_bim_need_signal"),
    RubricFactor("hiring_capacity_trigger", 10, _hiring_trigger_score,      "hiring_trigger"),
    RubricFactor("decision_maker_access",    5, _decision_maker_score,      "decision_maker_access"),
    RubricFactor("outsourcing_readiness",    5, _outsourcing_readiness_score, "outsourcing_readiness"),
    RubricFactor("commercial_attractiveness", 5, _commercial_attractiveness_score, "commercial_attractiveness"),
]

# Sanity check: weights must sum to 100
assert sum(f.weight for f in RUBRIC_FACTORS) == 100, "Rubric weights must sum to 100"
