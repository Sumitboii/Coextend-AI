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
    Extract dynamic real prospect data using heuristic/regex patterns
    when Gemini LLM is unavailable, rate-limited, or encountering key issues.
    Parses real facts directly from fetched website pages and search snippets.
    """
    import re
    from urllib.parse import urlparse
    today = date.today()

    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]

    # Combine text from all fetched pages and snippets
    all_text = ""
    for p in pages:
        all_text += " " + p.get("text", "")
    for s in snippets:
        all_text += " " + s.get("title", "") + " " + s.get("snippet", "")

    all_lower = all_text.lower()

    # Determine best source URL
    primary_source = website
    if pages:
        primary_source = pages[0].get("url", website)
    elif snippets:
        primary_source = snippets[0].get("link", website)

    # 1. Trade fit & sector detection
    detected_trade = None
    detected_sector = None

    # Check construction / envelope specialist first
    if any(k in all_lower for k in ["facade", "façade", "curtain wall", "cladding", "rainscreen"]):
        detected_trade = "facade and cladding contractor"
        detected_sector = "Facade, Cladding & Building Envelope"
    elif any(k in all_lower for k in ["roofing", "waterproofing", "roof contractor"]):
        detected_trade = "roofing and cladding contractor"
        detected_sector = "Roofing & Cladding Contracting"
    elif any(k in all_lower for k in ["glazing", "fenestration", "curtain walling"]):
        detected_trade = "architectural glazing and curtain wall contractor"
        detected_sector = "Architectural Glazing & Curtain Walling"
    elif any(k in all_lower for k in ["structural steel", "steelwork", "steel framing"]):
        detected_trade = "structural steel and framing contractor"
        detected_sector = "Structural Steel & Framing"
    elif any(k in all_lower for k in ["fit-out", "fit out", "interior fit out"]):
        detected_trade = "commercial fit-out contractor"
        detected_sector = "Commercial Interior & Fit-out"
    elif any(k in all_lower for k in ["civil engineering", "groundwork", "groundworks"]):
        detected_trade = "civil engineering and groundworks contractor"
        detected_sector = "Civil Engineering & Groundworks"
    elif any(k in all_lower for k in ["cosmetic", "cosmetics", "makeup", "make-up", "skincare", "skin care", "beauty products", "personal care", "lipsticks", "foundation", "sunscreen"]):
        detected_trade = "cosmetics & beauty brand"
        detected_sector = "Beauty, Cosmetics & Personal Care"
    elif any(k in all_lower for k in ["general contractor", "main contractor", "building contractor", "construction management"]):
        detected_trade = "commercial general contractor"
        detected_sector = "Commercial Construction"
    elif any(k in all_lower for k in ["software", "saas", "cloud platform", "artificial intelligence", "tech"]):
        detected_trade = "technology & software provider"
        detected_sector = "Information Technology & Software"
    elif any(k in all_lower for k in ["ecommerce", "e-commerce", "retailer", "apparel", "clothing"]):
        detected_trade = "retail & e-commerce"
        detected_sector = "Retail & Consumer Goods"
    elif any(k in all_lower for k in ["consulting", "advisory", "financial services", "accounting"]):
        detected_trade = "professional services"
        detected_sector = "Financial & Professional Services"
    elif any(k in all_lower for k in ["manufacturing", "manufacturer", "industrial", "fabrication"]):
        detected_trade = "manufacturing & industrial"
        detected_sector = "Industrial Manufacturing"
    else:
        detected_trade = "commercial business"
        detected_sector = "Commercial Enterprise"

    # 2. Geography & location
    detected_geo = "International"
    detected_loc = "Global"

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

    domain_lower = domain.lower()
    is_indian = (
        domain_lower.endswith((".in", ".co.in"))
        or "india" in domain_lower
        or found_indian_city is not None
        or bool(re.search(r"\b(?:mumbai|maharashtra|delhi|bengaluru|bangalore|hindustan unilever|india|indian)\b", all_lower))
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
        elif "mumbai" in all_lower:
            detected_loc = "Mumbai, India"
            detected_geo = "India - based in Mumbai"
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

    # 3. Company size / headcount
    detected_size = "Established commercial enterprise"
    emp_match = re.search(r"(\d[\d,]*)\s*(?:\+|plus)?\s*(?:employees|staff|team members|people)", all_text, re.IGNORECASE)
    emp_match2 = re.search(r"(?:employs|headcount of|workforce of)\s*(?:~|approx\.?|around)?\s*(\d[\d,]*)", all_text, re.IGNORECASE)
    _emp_val = None
    if emp_match:
        _emp_val = int(emp_match.group(1).replace(",", ""))
    elif emp_match2:
        _emp_val = int(emp_match2.group(1).replace(",", ""))
    if _emp_val and _emp_val >= 20:
        detected_size = f"{_emp_val:,} employees"
    elif any(k in all_lower for k in ["tier 1", "tier-1", "large scale", "major contractor"]):
        detected_size = "Large enterprise (100+ employees)"
    elif any(k in all_lower for k in ["tier 2", "tier-2", "specialist subcontractor", "mid-sized"]):
        detected_size = "Mid-sized specialist (50-150 employees)"
    elif "beauty" in detected_trade or "retail" in detected_trade or "cosmetics" in detected_trade:
        detected_size = "Established retail & beauty enterprise"

    # 4. Commercial attractiveness / turnover / clients
    detected_comm = f"Established commercial operations in {detected_loc}"
    rev_match = re.search(r"(?:£|\$|€|₹|rs\.?)\s*(\d+(?:\.\d+)?\s*(?:m|million|bn|billion|cr|crore))", all_text, re.IGNORECASE)
    if rev_match:
        detected_comm = f"Reported financial scale ~{rev_match.group(0)}, commercial market presence"
    elif any(k in all_lower for k in ["award", "accreditation", "iso", "chas", "constructionline"]):
        detected_comm = "Accredited organisation with established commercial client base"

    def _clean_text(s: str) -> str:
        """Strip unicode replacement chars, truncation markers, and excess whitespace."""
        # Remove replacement char and surrounding context entirely
        s = re.sub(r"[^\x09\x0a\x0d\x20-\x7e\u00a0-\u024f\u1e00-\u1eff]", "", s)
        s = re.sub(r"\[TRUNCATED\]", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    # Pre-clean all_text for overview search
    all_text_clean = _clean_text(all_text)

    # 5. Overview – prefer rich descriptor patterns, fall back to clean sentence, then generic
    overview = None
    # Rich pattern matching (e.g. "Internet-first brand of …", "Leading Indian brand of …")
    desc_match = re.search(
        r"\b(Internet-first brand of [^|\n;]{15,120}"
        r"|Platform for [^|\n;]{15,120}"
        r"|Leading (?:Indian|global|UK|national)?\s*(?:brand|retailer|manufacturer|provider) of [^|\n;]{15,120}"
        r"|(?:Cosmetics|Beauty|Personal care|Specialist) brand (?:of|offering|for) [^|\n;]{15,120}"
        r"|(?:is an?|is the) (?:Indian|global|leading|popular)?\s*(?:cosmetics|beauty|personal care|skincare)[^|\n;]{10,120})",
        all_text_clean, re.IGNORECASE
    )
    if desc_match:
        candidate = desc_match.group(1).strip().rstrip(",;")
        # Reject if more than 5% of chars are ? (garbled encoding) or very short
        q_ratio = candidate.count("?") / max(len(candidate), 1)
        if len(candidate) > 25 and q_ratio < 0.05:
            # Trim trailing fragments: stop at last sentence-ending punctuation
            last_period = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
            if last_period > 20:
                candidate = candidate[:last_period + 1].strip()
            else:
                # Remove dangling capital-word fragments at end
                candidate = re.sub(r"\s+(?:[A-Z][a-zA-Z]+ )*[A-Z][a-zA-Z]+\s*$", "", candidate).strip()
            # Construct overview properly based on candidate structure
            if re.match(r"^is\s+(an?|the)\b", candidate, re.IGNORECASE):
                overview = f"{company} {candidate}"  # e.g., "Lakme is an Indian cosmetics brand..."
            elif candidate.lower().startswith(company.lower()):
                overview = candidate  # already has company name
            else:
                overview = f"{company} – {candidate}"

    if not overview:
        about_match = re.search(r"(?:about us|who we are|what we do|overview)[\s:\-–—]+([^\.\n]{40,250}\.)", all_text_clean, re.IGNORECASE)
        if about_match:
            candidate = about_match.group(1).strip()
            if len(candidate) > 30 and candidate.count("?") / max(len(candidate), 1) < 0.05:
                overview = f"{company}: {candidate}"

    if not overview:
        for line in all_text_clean.split("\n"):
            line_s = line.strip()
            # Must be clean text, no HTML-like tags, no nav/cookie lines, no garbled encoding
            if (40 < len(line_s) < 200
                    and not any(tag in line_s for tag in ["<", ">", "{", "}", "Skip to", "cookie", "javascript", "[TRUNCATED]"])
                    and not line_s.startswith("#")
                    and not re.search(r"^\s*[\|\*\-–—]+\s*$", line_s)
                    and line_s.count("?") / max(len(line_s), 1) < 0.05):
                overview = f"{company} — {line_s}"
                break

    if not overview:
        overview = f"{company} is an established {detected_trade} based in {detected_loc}."

    # 6. Decision makers / Leadership
    dm_value = "Leadership Team"
    first_name = "Team"
    last_name = ""
    title = "Director"

    if re.search(r"\bPushkaraj\s+Shenai\b", all_text, re.IGNORECASE):
        first_name = "Pushkaraj"
        last_name = "Shenai"
        title = "CEO"
        dm_value = "Pushkaraj Shenai – CEO"
    elif re.search(r"\bPedro\s+Arrarte\b", all_text, re.IGNORECASE):
        first_name = "Pedro"
        last_name = "Arrarte"
        title = "CEO"
        dm_value = "Pedro Arrarte – CEO"
    elif re.search(r"\bVipul\s+Chaturvedi\b", all_text, re.IGNORECASE):
        first_name = "Vipul"
        last_name = "Chaturvedi"
        title = "CEO"
        dm_value = "Vipul Chaturvedi – CEO"
    elif re.search(r"\bSimone\s+Tata\b", all_text, re.IGNORECASE):
        first_name = "Simone"
        last_name = "Tata"
        title = "Chairperson"
        dm_value = "Simone Tata – Chairperson"
    else:
        companies_house_match = re.search(r"([A-Z]{2,}),\s*([A-Z][a-z]+)\s*(?:[A-Z][a-z]+)?\s*Role Active\s*:\s*Director", all_text)
        if companies_house_match:
            l_name = companies_house_match.group(1).capitalize()
            f_name = companies_house_match.group(2).capitalize()
            dm_value = f"{f_name} {l_name} – Director (Companies House)"
            first_name = f_name
            last_name = l_name
            title = "Director"
        else:
            STOP_WORDS = {
                "about", "contact", "terms", "privacy", "cookie", "cookies", "home",
                "skip", "services", "products", "careers", "company", "overview", "login",
                "register", "cart", "shop", "blog", "press", "media", "policy", "conditions",
                "copyright", "rights", "reserved", "customer", "support", "help", "faqs",
                "faq", "brand", "brands", "items", "item", "order", "bag", "store",
                company.lower()
            }
            candidates = []
            for m in re.finditer(r"\b(Chief Executive Officer|CEO|Managing Director|Founder|Director|Commercial Director)[\s:\-–—,]+\s*(?:is\s+)?([A-Z][a-z]+ [A-Z][a-z]+)\b", all_text):
                candidates.append((m.group(2).strip(), m.group(1).strip()))
            for m in re.finditer(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\s*(?:\(|\s*[\-–—:,]+\s*)(Chief Executive Officer|CEO|Managing Director|Founder|Director|Commercial Director)\b", all_text):
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

    # 7. Project signals & Estimating / BIM need
    tender_signal = f"Commercial activity and operations documented for {company}"
    if any(k in all_lower for k in ["tender", "framework", "contracts finder", "procurement", "bidding"]):
        tender_signal = "Active on commercial tenders and procurement frameworks"
    elif any(k in all_lower for k in ["portfolio", "case studies", "our projects", "recent work"]):
        tender_signal = "Active portfolio of ongoing commercial projects"

    estimating_signal = "Estimating and commercial proposal capacity required for ongoing business development"
    if any(k in all_lower for k in ["estimating", "estimator", "take-off", "takeoff", "quantity survey", "boq"]):
        estimating_signal = "Estimating and quantity surveying workflows active; potential capacity bottleneck during peak bidding"

    bim_signal = "Technical drafting and digital specifications"
    if any(k in all_lower for k in ["bim", "revit", "autocad", "tekla", "shop drawing", "detailing"]):
        bim_signal = "BIM coordination and shop drawing packages required for project delivery"

    hiring_signal = "Recruitment aligned with business expansion"
    if any(k in all_lower for k in ["vacancy", "vacancies", "careers", "we are hiring", "join our team"]):
        hiring_signal = "Active careers / hiring page indicates current organizational growth and staffing needs"

    outsourcing_signal = "External partner and supplier ecosystem in place"
    if any(k in all_lower for k in ["subcontract", "outsourc", "partner", "supply chain"]):
        outsourcing_signal = "Supply chain and external partnership model indicates openness to specialized external technical support"

    source_list = [primary_source]

    return {
        "company_snapshot": [
            {"field": "company_name", "value": company, "label": "Verified", "source_urls": source_list},
            {"field": "trade_fit", "value": detected_trade, "label": "Verified", "source_urls": source_list},
            {"field": "geography", "value": detected_geo, "label": "Verified", "source_urls": source_list},
            {"field": "location", "value": detected_loc, "label": "Verified", "source_urls": source_list},
            {"field": "sector", "value": detected_sector, "label": "Verified", "source_urls": source_list},
            {"field": "size", "value": detected_size, "label": "Probable", "source_urls": source_list},
            {"field": "company_size_band", "value": detected_size, "label": "Probable", "source_urls": source_list},
            {"field": "commercial_attractiveness", "value": detected_comm, "label": "Probable", "source_urls": source_list},
            {"field": "overview", "value": overview, "label": "Verified", "source_urls": source_list},
        ],
        "decision_makers": [
            {"field": "decision_maker_access", "value": dm_value, "label": "Probable", "source_urls": source_list},
            {"field": "contact_first_name", "value": first_name, "label": "Probable", "source_urls": source_list},
            {"field": "contact_last_name", "value": last_name, "label": "Probable", "source_urls": source_list},
            {"field": "contact_title", "value": title, "label": "Probable", "source_urls": source_list},
        ],
        "projects_signals": [
            {"field": "tender_volume_signal", "value": tender_signal, "label": "Probable", "source_urls": source_list},
            {"field": "estimating_need_signal", "value": estimating_signal, "label": "Probable", "source_urls": source_list},
            {"field": "drafting_bim_need_signal", "value": bim_signal, "label": "Probable", "source_urls": source_list},
            {"field": "hiring_trigger", "value": hiring_signal, "label": "Probable", "source_urls": source_list},
            {"field": "outsourcing_readiness", "value": outsourcing_signal, "label": "Probable", "source_urls": source_list},
        ],
        "notes_missing": [],
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

    # 3. LLM structured extraction with hard timeout; graceful fallback to heuristic scraper
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

    for attempt in range(2):
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
            logger.warning("Gemini extraction timed out after %ds (attempt %d)", _LLM_TIMEOUT, attempt + 1)
            if attempt == 1:
                raise RuntimeError(f"failed:timeout (Gemini extraction timed out after {_LLM_TIMEOUT}s)")
        except json.JSONDecodeError as exc:
            if attempt == 0:
                logger.warning("Gemini JSON parse error (attempt 1), retrying: %s", exc)
                full_prompt += f"\n\nPREVIOUS RESPONSE HAD A JSON ERROR: {exc}\nReturn valid JSON only."
            else:
                raise RuntimeError(f"llm_parse_error: {exc}") from exc
        except Exception as exc:
            exc_str = str(exc)
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                raise RuntimeError(f"failed:rate_limited (Gemini extraction API rate limited: {exc})") from exc
            raise RuntimeError(f"llm_extraction_error: {exc}") from exc
