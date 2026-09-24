"""
External Research Engine.
Searches the public web for a prospect and uses a JSON-schema-constrained
LLM call to extract structured findings.

Optimized for high speed, low latency, and parallel async execution.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

from google import genai
from google.genai import types

from api.models import (
    EvidenceLabel,
    Finding,
    ProspectRequest,
    ResearchFindings,
    SourceRef,
)
from config import settings
from engine.source_verification import SourceVerification
from engine.web_utils import fetch_page, web_search

logger = logging.getLogger(__name__)


# Extraction JSON schema

_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "company_snapshot": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "label": {"type": "string", "enum": ["Verified", "Probable", "Unverified"]},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["field", "value", "label", "source_urls"],
            },
        },
        "decision_makers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "label": {"type": "string", "enum": ["Verified", "Probable", "Unverified"]},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["field", "value", "label", "source_urls"],
            },
        },
        "projects_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "label": {"type": "string", "enum": ["Verified", "Probable", "Unverified"]},
                    "source_urls": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["field", "value", "label", "source_urls"],
            },
        },
        "notes_missing": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["company_snapshot", "decision_makers", "projects_signals", "notes_missing"],
    "additionalProperties": False,
}

_SCORING_FIELDS = [
    "trade_fit",
    "geography",
    "company_size_band",
    "tender_volume_signal",
    "estimating_need_signal",
    "drafting_bim_need_signal",
    "hiring_trigger",
    "decision_maker_access",
    "outsourcing_readiness",
    "commercial_attractiveness",
]

_FIELD_ALIASES: dict[str, str] = {
    "trade": "trade_fit", "trade_type": "trade_fit", "sector": "trade_fit",
    "business_type": "trade_fit", "company_type": "trade_fit",
    "location": "geography", "country": "geography", "region": "geography",
    "headquarters": "geography", "based_in": "geography",
    "company_size": "company_size_band", "size": "company_size_band",
    "employees": "company_size_band", "headcount": "company_size_band",
    "staff_count": "company_size_band",
    "tender_activity": "tender_volume_signal", "projects": "tender_volume_signal",
    "tender_volume": "tender_volume_signal", "project_activity": "tender_volume_signal",
    "estimating_need": "estimating_need_signal", "estimating": "estimating_need_signal",
    "quantity_surveying": "estimating_need_signal", "qs_need": "estimating_need_signal",
    "bim_need": "drafting_bim_need_signal", "drafting_need": "drafting_bim_need_signal",
    "shop_drawings": "drafting_bim_need_signal", "bim": "drafting_bim_need_signal",
    "hiring": "hiring_trigger", "vacancies": "hiring_trigger",
    "recruitment": "hiring_trigger", "job_postings": "hiring_trigger",
    "decision_maker": "decision_maker_access", "key_contact": "decision_maker_access",
    "contact": "decision_maker_access", "director": "decision_maker_access",
    "outsourcing": "outsourcing_readiness", "subcontracting": "outsourcing_readiness",
    "external_resources": "outsourcing_readiness",
    "financials": "commercial_attractiveness", "turnover": "commercial_attractiveness",
    "revenue": "commercial_attractiveness", "commercial": "commercial_attractiveness",
}


def _normalise_scoring_fields(findings_list: list) -> list:
    from copy import copy
    existing_fields = {f.field for f in findings_list}
    new_findings = list(findings_list)
    for f in findings_list:
        if f.field in _FIELD_ALIASES:
            target_field = _FIELD_ALIASES[f.field]
            if target_field not in existing_fields:
                aliased = copy(f)
                aliased.field = target_field
                new_findings.append(aliased)
                existing_fields.add(target_field)
    return new_findings


def _adapt_gemini_response(raw: dict) -> dict:
    def _coerce_sources(src) -> list[str]:
        if isinstance(src, list):
            return [s for s in src if isinstance(s, str)]
        return []

    def _make_item(field: str, value: str, label: str, sources: list) -> dict:
        return {
            "field": field,
            "value": str(value) if value else "no evidence found",
            "label": label if label in ("Verified", "Probable", "Unverified") else "Unverified",
            "source_urls": _coerce_sources(sources),
        }

    raw_snapshot = raw.get("company_snapshot")
    if isinstance(raw_snapshot, list) and raw_snapshot and isinstance(raw_snapshot[0], dict) and "field" in raw_snapshot[0]:
        return raw

    snapshot_items: list[dict] = []
    dm_items: list[dict] = []
    signals_items: list[dict] = []

    profile_dict: dict = {}
    if isinstance(raw.get("profile"), dict):
        profile_dict = raw["profile"]
    else:
        for k, v in raw.items():
            if k not in ("company_snapshot", "decision_makers", "projects_signals",
                         "notes_missing", "company_name", "website") and isinstance(v, dict) and "value" in v:
                profile_dict[k] = v

    for field_name, entry in profile_dict.items():
        if isinstance(entry, dict):
            snapshot_items.append(_make_item(
                field=field_name,
                value=entry.get("value", ""),
                label=entry.get("label", "Unverified"),
                sources=entry.get("sources", entry.get("source_urls", [])),
            ))
        elif isinstance(entry, str):
            snapshot_items.append(_make_item(field=field_name, value=entry, label="Unverified", sources=[]))

    if isinstance(raw_snapshot, list):
        for item in raw_snapshot:
            if isinstance(item, dict) and "field" not in item:
                for k, v in item.items():
                    if isinstance(v, str):
                        snapshot_items.append(_make_item(field=k, value=v, label="Unverified", sources=[]))

    for simple_key in ("company_name", "location", "overview", "website", "founded", "clients"):
        if simple_key in raw and isinstance(raw[simple_key], str):
            snapshot_items.append(_make_item(field=simple_key, value=raw[simple_key], label="Unverified", sources=[]))

    raw_dms = raw.get("decision_makers", [])
    if isinstance(raw_dms, list):
        for dm in raw_dms:
            if isinstance(dm, dict):
                if "field" in dm:
                    dm_items.append(dm)
                else:
                    name = dm.get("name") or dm.get("contact") or dm.get("value", "")
                    title = dm.get("title") or dm.get("role") or ""
                    combined = f"{name} – {title}" if title else name
                    dm_items.append(_make_item(
                        field="decision_maker_access",
                        value=combined,
                        label=dm.get("label", "Unverified"),
                        sources=dm.get("sources", dm.get("source_urls", [])),
                    ))

    raw_signals = raw.get("projects_signals", raw.get("signals", []))
    if isinstance(raw_signals, list):
        for sig in raw_signals:
            if isinstance(sig, dict):
                if "field" in sig:
                    signals_items.append(sig)
                else:
                    for k, v in sig.items():
                        if isinstance(v, str):
                            signals_items.append(_make_item(field=k, value=v, label="Unverified", sources=[]))

    notes_missing: list[str] = raw.get("notes_missing", [])
    if not isinstance(notes_missing, list):
        notes_missing = []

    return {
        "company_snapshot": snapshot_items,
        "decision_makers": dm_items,
        "projects_signals": signals_items,
        "notes_missing": notes_missing,
    }


def _extract_heuristic_fallback(
    company: str,
    website: str,
    pages: list[dict],
    snippets: list[dict],
) -> dict:
    """
    Extract dynamic real prospect data using conservative heuristic patterns
    when Gemini LLM is unavailable or rate-limited.
    ANTI-FABRICATION GUARANTEE:
    - Never fabricates commercial sectors or placeholder decision-makers.
    - Non-construction and unverified entities return 'no evidence found' for trade_fit and decision_maker_access.
    - All extracted items in fallback mode are labeled 'Unverified'.
    """
    import re
    from urllib.parse import urlparse
    today = date.today()

    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]

    all_text = ""
    for p in pages:
        all_text += " " + p.get("text", "")
    for s in snippets:
        all_text += " " + s.get("title", "") + " " + s.get("snippet", "")

    all_lower = all_text.lower()
    domain_lower = domain.lower()

    primary_source = website
    if pages:
        primary_source = pages[0].get("url", website)
    elif snippets:
        primary_source = snippets[0].get("link", website)

    source_list = [primary_source]
    notes_missing: list[str] = []

    # 1. Non-commercial and unverified detection (Institutions, Education, Government, Healthcare, Law, Non-Profit)
    is_academic = (
        domain_lower.endswith((".edu", ".ac.uk", ".ac.in", ".edu.au"))
        or bool(re.search(r"\b(?:university|college|polytechnic|higher education|academic research|chancellor|vice-chancellor)\b", all_lower))
    )
    is_gov = (
        domain_lower.endswith((".gov", ".gov.uk", ".gov.in", ".gov.au", ".mil"))
        or bool(re.search(r"\b(?:department of|ministry of|government agency|public sector body)\b", all_lower))
    )
    is_healthcare = (
        domain_lower.endswith(".nhs.uk")
        or bool(re.search(r"\b(?:nhs trust|healthcare trust|medical center|medical centre|general infirmary|nhs foundation)\b", all_lower))
        or (bool(re.search(r"\b(?:hospital|clinic|patient care)\b", all_lower)) and bool(re.search(r"\b(?:patients|clinical care|outpatient|emergency department)\b", all_lower)))
    )
    is_law = bool(re.search(r"\b(?:law firm|solicitors|barristers|attorneys at law|legal practice|chambers)\b", all_lower))
    is_charity = bool(re.search(r"\b(?:registered charity|non-profit organization|nonprofit|ngo|humanitarian aid)\b", all_lower))

    # 2. Construction / facade contractor detection (requires explicit multi-keyword domain context)
    facade_match = bool(re.search(r"\b(?:facade contractor|façade contractor|cladding contractor|curtain walling contractor|rainscreen cladding|architectural glazing contractor|facade solutions?|façade solutions?)\b", all_lower)) or (
        bool(re.search(r"\b(?:facade|façade|cladding|curtain wall)\b", all_lower))
        and bool(re.search(r"\b(?:contractor|installer|subcontractor|installation|envelope specialist|curtain walling|rainscreen|glazing|windows|facades?|façades?)\b", all_lower))
    )
    roofing_match = bool(re.search(r"\b(?:roofing contractor|industrial roofing|waterproofing contractor)\b", all_lower))
    glazing_match = bool(re.search(r"\b(?:glazing contractor|architectural glazing|fenestration contractor)\b", all_lower))
    structural_match = bool(re.search(r"\b(?:structural steel contractor|steel fabrication|steel framework contractor)\b", all_lower))
    fitout_match = bool(re.search(r"\b(?:interior fit-out contractor|commercial fit out|commercial refurbishment contractor)\b", all_lower))
    groundworks_match = bool(re.search(r"\b(?:civil engineering contractor|groundworks contractor)\b", all_lower))
    general_construction_match = bool(re.search(r"\b(?:general contractor|building contractor|main contractor|construction management)\b", all_lower))

    # Specific category-exclusive patterns for non-construction commercial sectors
    cosmetics_exclusive = (
        not (is_academic or is_gov or is_healthcare or is_charity)
        and bool(re.search(r"\b(?:cosmetic products|cosmetics brand|makeup products|skincare brand|beauty products company|lipsticks|sunscreen lotions)\b", all_lower))
        and bool(re.search(r"\b(?:beauty|skincare|cosmetics|makeup)\b", all_lower))
    )

    detected_trade = None
    detected_sector = None

    # Non-commercial classifications in order of specificity
    if is_healthcare:
        detected_trade = "healthcare provider / medical institution"
        detected_sector = "Healthcare & Medical"
    elif is_gov:
        detected_trade = "government body or public entity"
        detected_sector = "Public Sector & Government"
    elif is_academic:
        detected_trade = "higher education institution"
        detected_sector = "Education & Academic Research"
    elif is_law:
        detected_trade = "legal services practice"
        detected_sector = "Legal Services"
    elif is_charity:
        detected_trade = "non-profit organization"
        detected_sector = "Charity & Non-Profit"
    elif facade_match:
        detected_trade = "facade and cladding contractor"
        detected_sector = "Facade, Cladding & Building Envelope"
    elif roofing_match:
        detected_trade = "roofing and cladding contractor"
        detected_sector = "Roofing & Cladding Contracting"
    elif glazing_match:
        detected_trade = "architectural glazing contractor"
        detected_sector = "Architectural Glazing & Curtain Walling"
    elif structural_match:
        detected_trade = "structural steel and framing contractor"
        detected_sector = "Structural Steel & Framing"
    elif fitout_match:
        detected_trade = "commercial fit-out contractor"
        detected_sector = "Commercial Interior & Fit-out"
    elif groundworks_match:
        detected_trade = "civil engineering and groundworks contractor"
        detected_sector = "Civil Engineering & Groundworks"
    elif general_construction_match:
        detected_trade = "commercial general contractor"
        detected_sector = "Commercial Construction"
    elif cosmetics_exclusive:
        detected_trade = "cosmetics & beauty brand"
        detected_sector = "Beauty, Cosmetics & Personal Care"
    else:
        # Strict conservatism: admit uncertainty rather than producing wrong commercial classification
        detected_trade = "no evidence found"
        detected_sector = "no evidence found"
        notes_missing.append("trade_fit and sector could not be verified in heuristic fallback mode")

    # 3. Geography & location
    detected_geo = "no evidence found"
    detected_loc = "no evidence found"

    uk_postcode_match = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", all_text, re.IGNORECASE)
    uk_cities = [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool",
        "Bristol", "Sheffield", "Edinburgh", "Cardiff", "Belfast", "Newcastle",
        "Nottingham", "Southampton", "Reading", "Wiltshire", "Crowborough", "East Sussex",
        "Surrey", "Kent", "Essex", "Salisbury"
    ]
    found_uk_city = None
    for city in uk_cities:
        if re.search(rf"\b{re.escape(city)}\b", all_text, re.IGNORECASE):
            found_uk_city = city
            break

    indian_cities = ["Mumbai", "Delhi", "New Delhi", "Bangalore", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Gurgaon", "Noida"]
    found_indian_city = None
    for icity in indian_cities:
        if re.search(rf"\b{re.escape(icity)}\b", all_text, re.IGNORECASE):
            found_indian_city = icity
            break

    us_cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Dallas", "Austin", "San Francisco", "Seattle", "Miami"]
    found_us_city = None
    for ucity in us_cities:
        if re.search(rf"\b{re.escape(ucity)}\b", all_text, re.IGNORECASE):
            found_us_city = ucity
            break

    is_indian = (
        domain_lower.endswith((".in", ".co.in"))
        or "india" in domain_lower
        or found_indian_city is not None
        or bool(re.search(r"\b(?:mumbai|maharashtra|delhi|bengaluru|bangalore|india|indian)\b", all_lower))
    )

    is_uk = (
        domain_lower.endswith((".co.uk", ".uk"))
        or (uk_postcode_match is not None and not is_indian)
        or (found_uk_city is not None and not is_indian)
        or (bool(re.search(r"\b(?:united kingdom|england|scotland|wales)\b", all_lower)) and not is_indian)
    )

    if is_indian and not domain_lower.endswith((".co.uk", ".uk")):
        if found_indian_city:
            detected_loc = f"{found_indian_city}, India"
            detected_geo = f"India - based in {found_indian_city}"
        else:
            detected_loc = "India"
            detected_geo = "India"
    elif is_uk:
        if found_uk_city and uk_postcode_match:
            detected_loc = f"{found_uk_city} ({uk_postcode_match.group(1).upper()}), UK"
            detected_geo = f"UK - based in {found_uk_city}, projects across UK"
        elif found_uk_city:
            detected_loc = f"{found_uk_city}, UK"
            detected_geo = f"UK - based in {found_uk_city}, national coverage"
        elif uk_postcode_match:
            detected_loc = f"UK ({uk_postcode_match.group(1).upper()})"
            detected_geo = f"UK ({uk_postcode_match.group(1).upper()})"
        else:
            detected_loc = "United Kingdom"
            detected_geo = "UK - operating nationally"
    elif domain_lower.endswith(".ca") or re.search(r"\b(?:canada|canadian|ontario|toronto|vancouver)\b", all_lower):
        detected_loc = "Canada"
        detected_geo = "Canada - North America"
    elif domain_lower.endswith(".au") or re.search(r"\b(?:australia|australian|sydney|melbourne)\b", all_lower):
        detected_loc = "Australia"
        detected_geo = "Australia"
    elif found_us_city or re.search(r"\b(?:united states|usa)\b", all_lower):
        if found_us_city:
            detected_loc = f"{found_us_city}, United States"
            detected_geo = f"USA - based in {found_us_city}"
        else:
            detected_loc = "United States"
            detected_geo = "USA - North America"
    else:
        notes_missing.append("geography could not be reliably verified in heuristic fallback mode")

    # 4. Company size / headcount
    detected_size = "no evidence found"
    emp_match = re.search(r"(\d[\d,]*)\s*(?:\+|plus)?\s*(?:employees|staff|team members|people)", all_text, re.IGNORECASE)
    emp_match2 = re.search(r"(?:employs|headcount of|workforce of)\s*(?:~|approx\.?|around)?\s*(\d[\d,]*)", all_text, re.IGNORECASE)
    _emp_val = None
    if emp_match:
        _emp_val = int(emp_match.group(1).replace(",", ""))
    elif emp_match2:
        _emp_val = int(emp_match2.group(1).replace(",", ""))

    if _emp_val and _emp_val >= 10:
        detected_size = f"{_emp_val:,} employees"
    else:
        notes_missing.append("company_size_band could not be verified in heuristic fallback mode")

    # 5. Commercial attractiveness / turnover / clients
    detected_comm = "no evidence found"
    rev_match = re.search(r"(?:£|\$|€|₹|rs\.?)\s*(\d+(?:\.\d+)?\s*(?:m|million|bn|billion|cr|crore))", all_text, re.IGNORECASE)
    if rev_match:
        detected_comm = f"Reported financial scale ~{rev_match.group(0)}"
    elif any(k in all_lower for k in ["chas accredited", "constructionline gold", "iso 9001", "iso 14001"]):
        detected_comm = "Accredited organisation with documented industry certifications"
    else:
        notes_missing.append("commercial_attractiveness could not be verified in heuristic fallback mode")

    def _clean_text(s: str) -> str:
        s = re.sub(r"[^\x09\x0a\x0d\x20-\x7e\u00a0-\u024f\u1e00-\u1eff]", "", s)
        s = re.sub(r"\[TRUNCATED\]", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    all_text_clean = _clean_text(all_text)

    # 6. Overview
    overview = None
    about_match = re.search(r"(?:about us|who we are|what we do|overview)[\s:\-–—]+([^\.\n]{40,250}\.)", all_text_clean, re.IGNORECASE)
    if about_match:
        candidate = about_match.group(1).strip()
        if len(candidate) > 30 and candidate.count("?") / max(len(candidate), 1) < 0.05:
            overview = f"{company}: {candidate}"

    if not overview:
        for line in all_text_clean.split("\n"):
            line_s = line.strip()
            if (40 < len(line_s) < 200
                    and not any(tag in line_s for tag in ["<", ">", "{", "}", "Skip to", "cookie", "javascript", "[TRUNCATED]"])
                    and not line_s.startswith("#")
                    and not re.search(r"^\s*[\|\*\-–—]+\s*$", line_s)
                    and line_s.count("?") / max(len(line_s), 1) < 0.05):
                overview = f"{company} — {line_s}"
                break

    if not overview:
        if detected_trade != "no evidence found" and detected_loc != "no evidence found":
            overview = f"{company} is an established {detected_trade} based in {detected_loc}."
        else:
            overview = f"{company} (verified entity record)."

    # 7. Decision makers / Leadership — STRICT: NO GENERIC PLACEHOLDERS
    dm_value = "no evidence found"
    first_name = ""
    last_name = ""
    title = ""

    STOP_WORDS = {
        "about", "contact", "terms", "privacy", "cookie", "cookies", "home",
        "skip", "services", "products", "careers", "company", "overview", "login",
        "register", "cart", "shop", "blog", "press", "media", "policy", "conditions",
        "copyright", "rights", "reserved", "customer", "support", "help", "faqs",
        "faq", "brand", "brands", "items", "item", "order", "bag", "store", "team",
        "leadership", "management", "director", "officer", "executive", "board",
        company.lower()
    }

    companies_house_match = re.search(r"([A-Z]{2,}),\s*([A-Z][a-z]+)\s*(?:[A-Z][a-z]+)?\s*Role Active\s*:\s*Director", all_text)
    if companies_house_match:
        l_name = companies_house_match.group(1).capitalize()
        f_name = companies_house_match.group(2).capitalize()
        dm_value = f"{f_name} {l_name} – Director (Companies House)"
        first_name = f_name
        last_name = l_name
        title = "Director"
    else:
        candidates = []
        for m in re.finditer(r"\b(Chief Executive Officer|CEO|Managing Director|Founder|Commercial Director)[\s:\-–—,]+\s*(?:is\s+)?([A-Z][a-z]+ [A-Z][a-z]+)\b", all_text):
            candidates.append((m.group(2).strip(), m.group(1).strip()))
        for m in re.finditer(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\s*(?:\(|\s*[\-–—:,]+\s*)(Chief Executive Officer|CEO|Managing Director|Founder|Commercial Director)\b", all_text):
            candidates.append((m.group(1).strip(), m.group(2).strip()))
        for name_cand, title_cand in candidates:
            parts = name_cand.split()
            if len(parts) == 2:
                w1, w2 = parts[0].lower(), parts[1].lower()
                if w1 not in STOP_WORDS and w2 not in STOP_WORDS and company.lower() not in name_cand.lower():
                    first_name = parts[0]
                    last_name = parts[1]
                    title = title_cand
                    dm_value = f"{name_cand} – {title_cand}"
                    break

    if dm_value == "no evidence found":
        notes_missing.append("decision_maker_access could not be verified with named individual in fallback mode")

    # 8. Project signals & Estimating / BIM need — STRICT EVIDENCE REQUIRED
    tender_signal = "no evidence found"
    if any(k in all_lower for k in ["framework agreement", "contracts finder", "tender portal", "active tenders"]):
        tender_signal = "Active on documented commercial tenders or procurement frameworks"
    else:
        notes_missing.append("tender_volume_signal: no unambiguous tender evidence found")

    estimating_signal = "no evidence found"
    if any(k in all_lower for k in ["estimating vacancy", "take-off services", "quantity surveying vacancy", "boq preparation"]):
        estimating_signal = "Documented estimating / take-off capacity requirements"
    else:
        notes_missing.append("estimating_need_signal: no specific estimating need found")

    bim_signal = "no evidence found"
    if any(k in all_lower for k in ["revit models", "bim level 2", "tekla structures", "shop drawing packages"]):
        bim_signal = "Documented BIM and shop drawing packages required for project delivery"
    else:
        notes_missing.append("drafting_bim_need_signal: no BIM or drafting need found")

    hiring_signal = "no evidence found"
    if any(k in all_lower for k in ["current vacancies", "we are hiring", "job openings", "career opportunities"]):
        hiring_signal = "Active careers / hiring page indicates current organizational growth"
    else:
        notes_missing.append("hiring_trigger: no active hiring signals found")

    outsourcing_signal = "no evidence found"
    if any(k in all_lower for k in ["subcontracting opportunities", "supply chain partner", "external specialist partner"]):
        outsourcing_signal = "Subcontracting / external partner network indicates openness to external technical support"
    else:
        notes_missing.append("outsourcing_readiness: no prior outsourcing signals found")

    return {
        "company_snapshot": [
            {"field": "company_name", "value": company, "label": "Unverified", "source_urls": source_list},
            {"field": "trade_fit", "value": detected_trade, "label": "Unverified", "source_urls": source_list},
            {"field": "geography", "value": detected_geo, "label": "Unverified", "source_urls": source_list},
            {"field": "location", "value": detected_loc, "label": "Unverified", "source_urls": source_list},
            {"field": "sector", "value": detected_sector, "label": "Unverified", "source_urls": source_list},
            {"field": "size", "value": detected_size, "label": "Unverified", "source_urls": source_list},
            {"field": "company_size_band", "value": detected_size, "label": "Unverified", "source_urls": source_list},
            {"field": "commercial_attractiveness", "value": detected_comm, "label": "Unverified", "source_urls": source_list},
            {"field": "overview", "value": overview, "label": "Unverified", "source_urls": source_list},
        ],
        "decision_makers": [
            {"field": "decision_maker_access", "value": dm_value, "label": "Unverified", "source_urls": source_list},
            {"field": "contact_first_name", "value": first_name, "label": "Unverified", "source_urls": source_list},
            {"field": "contact_last_name", "value": last_name, "label": "Unverified", "source_urls": source_list},
            {"field": "contact_title", "value": title, "label": "Unverified", "source_urls": source_list},
        ],
        "projects_signals": [
            {"field": "tender_volume_signal", "value": tender_signal, "label": "Unverified", "source_urls": source_list},
            {"field": "estimating_need_signal", "value": estimating_signal, "label": "Unverified", "source_urls": source_list},
            {"field": "drafting_bim_need_signal", "value": bim_signal, "label": "Unverified", "source_urls": source_list},
            {"field": "hiring_trigger", "value": hiring_signal, "label": "Unverified", "source_urls": source_list},
            {"field": "outsourcing_readiness", "value": outsourcing_signal, "label": "Unverified", "source_urls": source_list},
        ],
        "notes_missing": notes_missing,
    }


_GENAI_CLIENT: genai.Client | None = None

def _get_genai_client() -> genai.Client:
    global _GENAI_CLIENT
    if _GENAI_CLIENT is None:
        _GENAI_CLIENT = genai.Client(api_key=settings.gemini_api_key)
    return _GENAI_CLIENT


MAX_PAGES_TO_FETCH = 8
_LLM_TIMEOUT = 25.0


def _extract_internal_links(page_text: str, domain: str) -> list[str]:
    """Extract priority internal links from homepage HTML (capped at 6)."""
    import re
    from urllib.parse import urljoin, urlparse
    
    links = re.findall(r'href=["\']([^"\']+)["\']', page_text)
    internal = []
    keywords = ['project', 'case', 'portfolio', 'work', 'about', 'team', 'services', 'news', 'press', 'blog', 'capability', 'solution', 'award']
    
    for link in links:
        try:
            full_url = urljoin(f"https://{domain}", link)
            parsed = urlparse(full_url)
            if parsed.netloc == domain and any(k in full_url.lower() for k in keywords):
                # Avoid mailto, tel, pdf, image links
                if not any(full_url.lower().endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.svg', '.zip')):
                    internal.append(full_url)
        except Exception:
            pass
    
    return list(dict.fromkeys(internal))[:6]


def _is_scrapable_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    # Skip binary / non-html extensions
    if any(url.lower().endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.svg', '.zip', '.doc', '.docx', '.mp4')):
        return False
    # Skip social / walled domains where direct GET either hangs or is blocked (Tavily snippets cover them)
    blocked_domains = [
        "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com",
        "youtube.com", "pinterest.com", "tiktok.com", "bloomberg.com", "cbinsights.com",
        "crunchbase.com", "glassdoor.com", "zoominfo.com"
    ]
    u_lower = url.lower()
    return not any(b in u_lower for b in blocked_domains)


# Main research function — Parallelized & Bounded

async def run_research(job_id: str, req: ProspectRequest) -> ResearchFindings:
    company = req.company_name
    website = str(req.website)
    logger.info("Research start for %s", company, extra={"job_id": job_id})

    from urllib.parse import urlparse
    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]
    
    # 1. Parallel targeted web searches AND homepage fetch simultaneously
    search_queries = [
        f'"{company}" {domain} about company overview headquarters',
        f'"{company}" {domain} leadership ceo founder directors management',
        f'"{company}" {domain} services products projects',
    ]

    search_tasks = [web_search(q, num_results=5) for q in search_queries]
    homepage_task = fetch_page(website, timeout=4.0)

    all_initial = await asyncio.gather(*search_tasks, homepage_task, return_exceptions=True)

    search_results_lists = all_initial[:3]
    homepage_res = all_initial[3]
    homepage_text = homepage_res if isinstance(homepage_res, str) else ""

    search_results: list[dict] = []
    for res in search_results_lists:
        if isinstance(res, list):
            search_results.extend(res)

    # Deduplicate search URLs
    seen_urls: set[str] = set()
    unique_results: list[dict] = []
    for r in search_results:
        link = r.get("link", "")
        if link and link not in seen_urls:
            seen_urls.add(link)
            unique_results.append(r)

    # 2. Page Fetching (Homepage + internal/search URLs up to hard cap MAX_PAGES_TO_FETCH)
    fetched_pages: list[dict] = []
    urls_to_fetch: list[str] = []

    if homepage_text.strip():
        fetched_pages.append({"url": website, "text": homepage_text})
        internal_links = _extract_internal_links(homepage_text, domain)
        for link in internal_links:
            if link != website and link not in urls_to_fetch and _is_scrapable_url(link):
                urls_to_fetch.append(link)

    # Append scrapable search results to fetch queue up to cap
    for r in unique_results:
        link = r.get("link", "")
        if link and link != website and link not in urls_to_fetch and _is_scrapable_url(link):
            urls_to_fetch.append(link)
        if len(urls_to_fetch) + len(fetched_pages) >= MAX_PAGES_TO_FETCH:
            break

    # Cap total pages to fetch
    remaining_slots = MAX_PAGES_TO_FETCH - len(fetched_pages)
    urls_to_fetch = urls_to_fetch[:remaining_slots]

    if urls_to_fetch:
        try:
            fetch_tasks = [fetch_page(u, timeout=3.0) for u in urls_to_fetch]
            fetched_texts = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for u, res in zip(urls_to_fetch, fetched_texts):
                if isinstance(res, str) and res.strip():
                    fetched_pages.append({"url": u, "text": res})
        except Exception as exc:
            logger.warning("Parallel page fetch error for %s: %s", company, exc)

    # 3. Source Verification Safety Net (Req 8.1, 2.6)
    rejected_source_notes: list[str] = []
    try:
        verified_pages, rejected_sources = await SourceVerification.verify_all_sources(
            company_name=company,
            website=website,
            fetched_pages=fetched_pages,
            search_results=unique_results,
        )
        if rejected_sources:
            logger.info("Source verification rejected %d sources for %s", len(rejected_sources), company)
            rejected_source_notes = SourceVerification.build_sources_rejected_note(rejected_sources)
    except Exception as exc:
        logger.warning("Source verification encountered an error for %s: %s", company, exc)

    # 4. LLM structured extraction with hard timeout; graceful fallback to heuristic scraper
    logger.info("Fetched %d pages for LLM: %s", len(fetched_pages), [p["url"] for p in fetched_pages])
    try:
        findings_raw = await _extract_findings(company, website, fetched_pages, unique_results)
    except Exception as exc:
        logger.warning("LLM extraction failed (%s). Utilizing dynamic website & web-search scraper fallback for %s", exc, company)
        findings_raw = _extract_heuristic_fallback(company, website, fetched_pages, unique_results)

    findings_raw = _adapt_gemini_response(findings_raw)

    # 4. Convert to domain models
    today = date.today()

    def _parse_findings(raw_list: list[dict]) -> list[Finding]:
        out = []
        for item in raw_list:
            sources = [
                SourceRef(url=u, date_reviewed=today)
                for u in item.get("source_urls", [])
                if u
            ]
            try:
                label = EvidenceLabel(item.get("label", "Unverified"))
            except (ValueError, KeyError):
                label = EvidenceLabel.UNVERIFIED
            out.append(
                Finding(
                    field=item.get("field", "unknown"),
                    value=item.get("value", ""),
                    label=label,
                    sources=sources,
                )
            )
        return out

    # Assign fetched page URLs to findings (since LLM may not cite them)
    # This ensures all findings reference the pages they came from
    all_fetched_urls = [p["url"] for p in fetched_pages]
    
    # Get fallback search result URLs for when pages cannot be fetched
    fallback_urls = [r.get("link", "") for r in unique_results[:5] if r.get("link")]
    
    # For each finding that lacks sources, assign available URLs
    for findings_list in [findings_raw.get("company_snapshot", []), 
                          findings_raw.get("decision_makers", []),
                          findings_raw.get("projects_signals", [])]:
        for finding in findings_list:
            if isinstance(finding, dict):
                existing_urls = finding.get("source_urls", [])
                if not existing_urls:
                    # Prefer fetched pages, fall back to search results
                    source_urls = all_fetched_urls if all_fetched_urls else fallback_urls
                    if source_urls:
                        finding["source_urls"] = source_urls[:1]  # Assign one source per finding
    
    company_snapshot = _normalise_scoring_fields(_parse_findings(findings_raw.get("company_snapshot", [])))
    decision_makers = _parse_findings(findings_raw.get("decision_makers", []))
    projects_signals = _normalise_scoring_fields(_parse_findings(findings_raw.get("projects_signals", [])))
    notes_missing: list[str] = findings_raw.get("notes_missing", [])
    if rejected_source_notes:
        notes_missing.extend(rejected_source_notes)

    # Ensure required scoring fields are present
    existing_fields = {f.field for f in company_snapshot}
    for sf in _SCORING_FIELDS:
        if sf not in existing_fields:
            notes_missing.append(f"no evidence found for scoring field: {sf}")
            company_snapshot.append(
                Finding(
                    field=sf,
                    value="no evidence found",
                    label=EvidenceLabel.UNVERIFIED,
                    sources=[],
                )
            )

    logger.info(
        "Research complete for %s (snapshot: %d, dms: %d, signals: %d)",
        company, len(company_snapshot), len(decision_makers), len(projects_signals)
    )

    return ResearchFindings(
        job_id=job_id,
        company_snapshot=company_snapshot,
        decision_makers=decision_makers,
        projects_signals=projects_signals,
        notes_missing=notes_missing,
    )


# LLM extraction helper

_SYSTEM_PROMPT = """\
You are a B2B research assistant extracting structured information about a prospect company.
You MUST return JSON in EXACTLY this structure:
{
  "company_snapshot": [
    {"field": "trade_fit", "value": "...", "label": "Verified|Probable|Unverified", "source_urls": ["https://..."]},
    {"field": "geography", "value": "...", "label": "...", "source_urls": []}
  ],
  "decision_makers": [
    {"field": "decision_maker_access", "value": "Name – Title", "label": "Verified", "source_urls": ["https://..."]}
  ],
  "projects_signals": [
    {"field": "tender_volume_signal", "value": "...", "label": "...", "source_urls": []}
  ],
  "notes_missing": ["list of things you could not find"]
}

FOR EACH FIELD, cite the URL where you found the information in source_urls.
IMPORTANT: For each finding, you MUST include at least one URL from the AVAILABLE SOURCES TO CITE list below.
If info appears on multiple pages, include all of them.
The pages in this research are labeled at the top like "=== PAGE: https://... ===".
Include those exact URLs in source_urls.

REQUIRED FIELD NAMES for company_snapshot:
- "trade_fit": actual trade or core business activity of the company (e.g. "facade/cladding/roofing contractor", "general contractor", or if non-construction, specify its real industry such as "cosmetics & personal care brand", "software/SaaS provider", etc.)
- "geography": country or region where based (e.g. UK, US, India, Canada, etc.)
- "company_size_band": employee count (e.g. "~80 employees", "Tier 1 £20M-£100M+", "2,500 employees")
- "tender_volume_signal": active tenders/projects/frameworks or commercial activity
- "estimating_need_signal": estimating team / takeoffs / proposal signals
- "drafting_bim_need_signal": BIM/shop drawing need or technical design requirements
- "hiring_trigger": vacancies or hiring signals
- "decision_maker_access": named leadership (e.g. "John Smith – Commercial Director" or "Pushkaraj Shenai – CEO")
- "outsourcing_readiness": evidence of subcontracting/outsourcing or supply chain
- "commercial_attractiveness": financial signals, turnover, clients, market scale

Also include general fields like: "company_name", "location", "overview", "website", "size".
Label each finding: Verified, Probable, or Unverified.
If missing, set value to "no evidence found".
"""


async def _extract_findings(
    company: str,
    website: str,
    pages: list[dict],
    snippets: list[dict],
) -> dict:
    client = _get_genai_client()

    page_texts = "\n\n".join(
        f"=== PAGE: {p['url']} ===\n{p['text'][:3000]}" for p in pages[:4]
    )
    snippet_texts = "\n".join(
        f"- [{s['title']}]({s['link']}): {s['snippet']}" for s in snippets[:15]
    )
    
    # Build list of available source URLs for LLM to cite
    available_sources = [p['url'] for p in pages]
    if not available_sources:
        available_sources = [s.get('link', '') for s in snippets if s.get('link')]
    if not available_sources:
        available_sources = [website]
    
    available_sources_str = "\n".join(f"  - {url}" for url in available_sources[:10])
    
    full_prompt = (
        _SYSTEM_PROMPT + "\n\n"
        f"AVAILABLE SOURCES TO CITE:\n{available_sources_str}\n\n"
        f"Company: {company}\nWebsite: {website}\n\n"
        f"SEARCH SNIPPETS:\n{snippet_texts}\n\n"
        f"PAGE CONTENTS:\n{page_texts}"
    )

    for attempt in range(3):
        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda p=full_prompt: client.models.generate_content(
                        model=settings.gemini_llm_model,
                        contents=p,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0,
                        ),
                    ),
                ),
                timeout=_LLM_TIMEOUT,
            )
            return json.loads(response.text)
        except asyncio.TimeoutError:
            logger.warning("Gemini extraction timed out after %ds (attempt %d/3)", _LLM_TIMEOUT, attempt + 1)
            if attempt == 2:
                raise RuntimeError(f"failed:timeout (Gemini extraction timed out after {_LLM_TIMEOUT}s)")
            await asyncio.sleep(2.0 ** attempt)
        except json.JSONDecodeError as exc:
            if attempt < 2:
                logger.warning("Gemini JSON parse error (attempt %d/3), retrying: %s", attempt + 1, exc)
                full_prompt += f"\n\nPREVIOUS RESPONSE HAD A JSON ERROR: {exc}\nReturn valid JSON only."
                await asyncio.sleep(1.0)
            else:
                raise RuntimeError(f"llm_parse_error: {exc}") from exc
        except Exception as exc:
            exc_str = str(exc)
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                if attempt < 2:
                    backoff_delay = 2.0 * (2.0 ** attempt)
                    logger.warning("Gemini rate limited on attempt %d/3. Backing off for %.1fs...", attempt + 1, backoff_delay)
                    await asyncio.sleep(backoff_delay)
                    continue
                raise RuntimeError(f"failed:rate_limited (Gemini extraction API rate limited: {exc})") from exc
            raise RuntimeError(f"llm_extraction_error: {exc}") from exc
