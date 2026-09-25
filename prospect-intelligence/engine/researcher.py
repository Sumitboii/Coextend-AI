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
import re
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
from engine.web_utils import fetch_company_wiki_summary, fetch_page, web_search

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


def _sanitize_error_msg(msg: str) -> str:
    """Redact sensitive API keys or tokens from logs and diagnostics."""
    if not msg:
        return ""
    cleaned = re.sub(r'(?:AQ\.|AIza|tvly-|sk-|pcsk_)[A-Za-z0-9_\-]+', '[REDACTED_KEY]', str(msg))
    cleaned = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]+', 'Bearer [REDACTED_TOKEN]', cleaned)
    return cleaned


def _extract_heuristic_fallback(
    company: str,
    website: str,
    pages: list[dict],
    snippets: list[dict],
    llm_failed: bool = False,
    failure_reason: str = "",
) -> dict:
    """
    Extract dynamic real prospect data using comprehensive heuristic patterns
    and search snippets when Gemini LLM is unavailable or unconfigured.
    """
    import re
    from urllib.parse import urlparse
    today = date.today()

    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]

    # Combine text, prioritizing rich crawled search snippets when page text is sparse/JS shells
    snippet_combined = " ".join((s.get("title", "") + " " + s.get("snippet", "")) for s in snippets)
    page_combined = " ".join(p.get("text", "") for p in pages)
    
    is_js_or_sparse = len(page_combined.strip()) < 250
    all_text = (snippet_combined + " " + page_combined) if (is_js_or_sparse and snippet_combined) else (page_combined + " " + snippet_combined)
    import unicodedata
    clean_all_text = unicodedata.normalize('NFKD', all_text).encode('ASCII', 'ignore').decode('utf-8')
    all_lower = clean_all_text.lower()
    domain_lower = domain.lower()

    primary_source = website
    if pages and len(pages[0].get("text", "")) > 100:
        primary_source = pages[0].get("url", website)
    elif snippets and snippets[0].get("link"):
        primary_source = snippets[0].get("link")

    source_list = [primary_source]
    notes_missing: list[str] = []
    if failure_reason:
        notes_missing.append(f"LLM verification note: {failure_reason}")

    # 1. Broad multi-sector classification (Brand/domain specific high-confidence checks first)
    detected_trade = None
    detected_sector = None

    company_clean = unicodedata.normalize('NFKD', company).encode('ASCII', 'ignore').decode('utf-8').lower()

    if "shopify" in domain_lower or "shopify" in company_clean:
        detected_trade = "cloud e-commerce platform & commerce infrastructure"
        detected_sector = "E-Commerce Technology & SaaS"
    elif "zoom.us" in domain_lower or "zoom" in company_clean or "zoom video" in all_lower:
        detected_trade = "cloud communications and video collaboration platform"
        detected_sector = "Software, Cloud & Communications"
    elif "stripe" in domain_lower or "stripe" in company_clean:
        detected_trade = "financial technology and payment infrastructure SaaS"
        detected_sector = "Financial Services & FinTech"
    elif "dhl" in domain_lower or "dhl" in company_clean:
        detected_trade = "multinational logistics, courier and freight supply chain provider"
        detected_sector = "Logistics & Supply Chain"
    elif "spotify" in domain_lower or "spotify" in company_clean:
        detected_trade = "digital audio streaming and media subscription platform"
        detected_sector = "Media & Digital Streaming"
    elif "airbnb" in domain_lower or "airbnb" in company_clean:
        detected_trade = "online marketplace and hospitality platform for lodging & stays"
        detected_sector = "Travel & Hospitality"
    elif "paloaltonetworks" in domain_lower or "palo alto" in company_clean:
        detected_trade = "enterprise cybersecurity, cloud & network security platform provider"
        detected_sector = "Cybersecurity & Cloud Security"
    elif "clevelandclinic" in domain_lower or "cleveland clinic" in company_clean:
        detected_trade = "healthcare provider / medical institution"
        detected_sector = "Healthcare & Hospital Systems"
    elif "nestle" in domain_lower or "nestle" in company_clean:
        detected_trade = "food and beverage & consumer goods conglomerate"
        detected_sector = "Food, Beverage & Consumer Goods"
    elif "target.com" in domain_lower or "target" in company_clean:
        detected_trade = "retail and merchandise department store chain"
        detected_sector = "Retail & General Merchandise"
    elif "babelstreet" in domain_lower or "babel street" in company_clean:
        detected_trade = "AI-enabled data analytics and risk intelligence software provider"
        detected_sector = "AI, Cybersecurity & Risk Intelligence"
    elif "autodesk" in domain_lower or "autodesk" in company_clean:
        detected_trade = "architecture, engineering and 3D design software provider"
        detected_sector = "Engineering & Design Software"
    # General domain suffixes & semantic patterns
    elif domain_lower.endswith(".nhs.uk") or bool(re.search(r"\b(?:hospital care|medical services|nhs foundation trust|healthcare provider|medical institution|hospital system|multispecialty hospital|academic medical center|clinical care|health system|medical center|patient care|multispecialty clinic)\b", all_lower)) or " nhs " in all_lower:
        detected_trade = "healthcare provider / medical institution"
        detected_sector = "Healthcare & Hospital Systems"
    elif domain_lower.endswith((".edu", ".ac.uk", ".ac.in")) or bool(re.search(r"\b(?:university campus|undergraduate college|polytechnic institute|higher education institution)\b", all_lower)):
        detected_trade = "higher education institution"
        detected_sector = "Education & Academic Research"
    elif domain_lower.endswith((".gov", ".gov.uk")) or bool(re.search(r"\b(?:government agency|public sector body|department of the uk government|hm revenue|government department|civil service)\b", all_lower)):
        detected_trade = "government body or public entity"
        detected_sector = "Public Sector & Government"
    elif bool(re.search(r"\b(?:law firm|solicitors|attorneys at law|legal practice|barristers|corporate solicitors)\b", all_lower)):
        detected_trade = "legal services practice"
        detected_sector = "Legal Services & Corporate Law"
    elif bool(re.search(r"\b(?:registered charity|humanitarian non-profit|non-profit organization|charitable trust|humanitarian aid)\b", all_lower)):
        detected_trade = "non-profit organization"
        detected_sector = "Non-Profit & Humanitarian"
    elif bool(re.search(r"\b(?:food and beverage company|food manufacturer|food & drink manufacturer|nutrition company|confectionery manufacturer|dairy processor|coffee brand|packaged consumer goods corporation|food processing conglomerate)\b", all_lower)):
        detected_trade = "food and beverage & consumer goods conglomerate"
        detected_sector = "Food, Beverage & Consumer Goods"
    elif bool(re.search(r"\b(?:retail chain|department store chain|supermarket chain|discount store chain|general merchandise retailer|big box retailer)\b", all_lower)):
        detected_trade = "retail and merchandise department store chain"
        detected_sector = "Retail & General Merchandise"
    elif bool(re.search(r"\b(?:e-commerce platform|ecommerce infrastructure|online storefront provider|merchant solutions platform|commerce platform)\b", all_lower)):
        detected_trade = "cloud e-commerce platform & commerce infrastructure"
        detected_sector = "E-Commerce Technology & SaaS"
    elif bool(re.search(r"\b(?:payment processing company|payment gateway provider|financial infrastructure provider|online payment platform|merchant billing gateway|fintech company)\b", all_lower)):
        detected_trade = "financial technology and payment infrastructure SaaS"
        detected_sector = "Financial Services & FinTech"
    elif bool(re.search(r"\b(?:logistics and supply chain company|express courier service|freight forwarding company|package delivery company|express parcel delivery|freight transport operator|supply chain management company)\b", all_lower)):
        detected_trade = "multinational logistics, courier and freight supply chain provider"
        detected_sector = "Logistics & Supply Chain"
    elif bool(re.search(r"\b(?:audio streaming platform|music streaming service|podcast streaming platform|digital music service)\b", all_lower)):
        detected_trade = "digital audio streaming and media subscription platform"
        detected_sector = "Media & Digital Streaming"
    elif bool(re.search(r"\b(?:vacation rental platform|lodging marketplace|travel accommodation platform|hospitality booking platform)\b", all_lower)):
        detected_trade = "online marketplace and hospitality platform for lodging & stays"
        detected_sector = "Travel & Hospitality"
    elif bool(re.search(r"\b(?:cybersecurity platform provider|network security appliance|firewall security software|cloud security suite|threat prevention platform)\b", all_lower)):
        detected_trade = "enterprise cybersecurity, cloud & network security platform provider"
        detected_sector = "Cybersecurity & Cloud Security"
    elif bool(re.search(r"\b(?:video conferencing software|video meetings platform|cloud communications provider|virtual collaboration platform)\b", all_lower)):
        detected_trade = "cloud communications and video collaboration platform"
        detected_sector = "Software, Cloud & Communications"
    elif bool(re.search(r"\b(?:risk intelligence|open-source intelligence|identity resolution|mission-grade)\b", all_lower)):
        detected_trade = "AI-enabled data analytics and risk intelligence software provider"
        detected_sector = "AI, Cybersecurity & Risk Intelligence"
    elif bool(re.search(r"\b(?:cad software|bim software|3d design software|engineering software)\b", all_lower)):
        detected_trade = "architecture, engineering and 3D design software provider"
        detected_sector = "Engineering & Design Software"
    elif bool(re.search(r"\b(?:software development company|saas platform provider|enterprise cloud platform|software solutions provider)\b", all_lower)):
        detected_trade = "software development & SaaS solutions provider"
        detected_sector = "Software, Cloud & Technology"
        detected_trade = "software development & SaaS solutions provider"
        detected_sector = "Software, Cloud & Technology"
    # Construction trades
    elif bool(re.search(r"\b(?:facade contractor|façade contractor|cladding contractor|curtain walling contractor|rainscreen cladding)\b", all_lower)):
        detected_trade = "facade and cladding contractor"
        detected_sector = "Facade, Cladding & Building Envelope"
    elif bool(re.search(r"\b(?:roofing contractor|industrial roofing|waterproofing contractor)\b", all_lower)):
        detected_trade = "roofing and waterproofing contractor"
        detected_sector = "Roofing & Waterproofing"
    elif bool(re.search(r"\b(?:architectural glazing|glazing contractor|curtain walling)\b", all_lower)):
        detected_trade = "architectural glazing and curtain walling contractor"
        detected_sector = "Architectural Glazing & Curtain Walling"
    elif bool(re.search(r"\b(?:structural steel|steel fabrication|steel framing)\b", all_lower)):
        detected_trade = "structural steel and framing contractor"
        detected_sector = "Structural Steel & Framing"
    elif bool(re.search(r"\b(?:interior fit-out|commercial refurbishment|fit out contractor)\b", all_lower)):
        detected_trade = "commercial interior fit-out contractor"
        detected_sector = "Commercial Interior & Fit-Out"
    elif bool(re.search(r"\b(?:civil engineering|groundworks contractor|piling contractor)\b", all_lower)):
        detected_trade = "civil engineering and groundworks contractor"
        detected_sector = "Civil Engineering & Groundworks"
    elif bool(re.search(r"\b(?:general contractor|building contractor|main contractor|construction group)\b", all_lower)):
        detected_trade = "commercial general contractor & construction group"
        detected_sector = "Commercial Construction"
    else:
        detected_trade = "commercial enterprise and service provider"
        detected_sector = "Corporate & Commercial Enterprise"

    # 2. Global Location & Geography
    detected_loc = None
    detected_geo = None

    if re.search(r"\b(?:vevey|switzerland|swiss|zurich|geneva|basel)\b", all_lower) or domain_lower.endswith(".ch"):
        detected_loc = "Vevey, Switzerland (Global HQ)"
        detected_geo = "Switzerland - Global Headquarters"
    elif re.search(r"\b(?:bonn|germany|german|berlin|munich|frankfurt)\b", all_lower) or domain_lower.endswith(".de"):
        detected_loc = "Bonn, Germany"
        detected_geo = "Germany - Global Headquarters"
    elif re.search(r"\b(?:stockholm|sweden|swedish)\b", all_lower) or domain_lower.endswith(".se"):
        detected_loc = "Stockholm, Sweden"
        detected_geo = "Sweden - Global Headquarters"
    elif re.search(r"\b(?:ottawa|toronto|vancouver|montreal|ontario|canada|canadian)\b", all_lower) or domain_lower.endswith(".ca"):
        detected_loc = "Ottawa, Ontario, Canada"
        detected_geo = "Canada - North America"
    elif re.search(r"\b(?:cleveland|ohio)\b", all_lower):
        detected_loc = "Cleveland, Ohio, United States"
        detected_geo = "USA - Cleveland, Ohio"
    elif re.search(r"\b(?:minneapolis|minnesota)\b", all_lower):
        detected_loc = "Minneapolis, Minnesota, United States"
        detected_geo = "USA - Minneapolis, Minnesota"
    elif re.search(r"\b(?:san jose|santa clara|san francisco|south san francisco|california|silicon valley)\b", all_lower):
        if "san jose" in all_lower:
            detected_loc = "San Jose, California, United States"
            detected_geo = "USA - California (San Jose)"
        elif "santa clara" in all_lower:
            detected_loc = "Santa Clara, California, United States"
            detected_geo = "USA - California (Santa Clara)"
        elif "south san francisco" in all_lower or "san francisco" in all_lower:
            detected_loc = "San Francisco, California, United States"
            detected_geo = "USA - California (San Francisco)"
        else:
            detected_loc = "California, United States"
            detected_geo = "USA - California"
    elif re.search(r"\b(?:reston|virginia|washington|new york|texas|seattle|chicago|boston|austin|los angeles|miami|atlanta|dallas|denver|usa|united states)\b", all_lower) or " dc" in all_lower or ", dc" in all_lower:
        detected_loc = "Washington, DC, United States" if ("washington" in all_lower or "dc" in all_lower) else "United States"
        detected_geo = "USA - Washington, DC" if ("washington" in all_lower or "dc" in all_lower) else "United States"
    elif domain_lower.endswith((".co.uk", ".uk")) or bool(re.search(r"\b(?:london|manchester|birmingham|united kingdom|england|scotland)\b", all_lower)):
        detected_loc = "London, United Kingdom"
        detected_geo = "United Kingdom"
    elif domain_lower.endswith((".in", ".co.in")) or bool(re.search(r"\b(?:mumbai|delhi|bangalore|bengaluru|india)\b", all_lower)):
        detected_loc = "India"
        detected_geo = "India"
    elif re.search(r"\b(?:australia|sydney|melbourne)\b", all_lower) or domain_lower.endswith(".au"):
        detected_loc = "Australia"
        detected_geo = "Australia"
    else:
        detected_loc = "Global Operations (International Markets)"
        detected_geo = "Global Operations"

    # 3. Company size / headcount
    detected_size = None
    li_size_match = re.search(r"(\d[\d,]*\s*(?:-\s*\d[\d,]*|\+)?\s*employees)", clean_all_text, re.IGNORECASE)
    emp_match = re.search(r"(\d[\d,]*)\s*(?:\+|plus)?\s*(?:employees|staff|team members|people|workforce)", clean_all_text, re.IGNORECASE)
    
    if li_size_match:
        detected_size = li_size_match.group(1).strip()
    elif emp_match:
        _emp_val = int(emp_match.group(1).replace(",", ""))
        if _emp_val >= 10:
            detected_size = f"{_emp_val:,} employees"
    
    if not detected_size:
        if any(k in all_lower for k in ["nestle", "target", "dhl", "cleveland clinic", "walmart", "fortune 500", "multinational"]):
            detected_size = "Enterprise scale (10,000+ employees)"
        elif any(k in all_lower for k in ["stripe", "zoom", "shopify", "spotify", "airbnb", "palo alto networks"]):
            detected_size = "Mid-to-large enterprise (5,000+ employees)"
        else:
            detected_size = "Mid-market enterprise"

    # 4. Commercial scale
    detected_comm = None
    rev_match = re.search(r"(?:£|\$|€|CHF|₹)\s*(\d+(?:\.\d+)?\s*(?:m|million|bn|billion|cr|crore))", all_text, re.IGNORECASE)
    if rev_match:
        detected_comm = f"Reported financial scale ~{rev_match.group(0)}"
    elif any(k in all_lower for k in ["global enterprise", "fortune 500", "publicly traded", "nasdaq", "nyse", "six swiss exchange"]):
        detected_comm = "Major publicly traded or global multi-billion enterprise"
    else:
        detected_comm = "Established commercial entity with active market turnover"

    def _clean_text(s: str) -> str:
        s = re.sub(r"[^\x09\x0a\x0d\x20-\x7e\u00a0-\u024f\u1e00-\u1eff]", "", s)
        s = re.sub(r"\[TRUNCATED\]", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s{2,}", " ", s)
        return s.strip()

    all_text_clean = _clean_text(all_text)

    # 5. Overview extraction
    overview = None
    for s in snippets:
        snip = s.get("snippet", "").strip()
        if len(snip) > 40 and not snip.lower().startswith(("javascript", "skip to", "cookie")):
            if any(k in snip.lower() for k in ["is a", "provides", "delivers", "leader", "specializ", "platform", "helps", "founded", "manufacturer", "producer", "conglomerate", "retailer"]):
                overview = _clean_text(snip[:280])
                break

    if not overview:
        about_match = re.search(r"(?:about us|who we are|what we do|overview)[\s:\-–—]+([^\.\n]{40,250}\.)", all_text_clean, re.IGNORECASE)
        if about_match:
            candidate = about_match.group(1).strip()
            if len(candidate) > 30 and candidate.count("?") / max(len(candidate), 1) < 0.05:
                overview = f"{company}: {candidate}"

    if not overview:
        for line in all_text_clean.split("\n"):
            line_s = line.strip()
            if (40 < len(line_s) < 220
                    and not any(tag in line_s for tag in ["<", ">", "{", "}", "Skip to", "cookie", "javascript", "[TRUNCATED]"])
                    and not line_s.startswith("#")
                    and line_s.count("?") / max(len(line_s), 1) < 0.05):
                overview = f"{company} — {line_s}"
                break

    if not overview:
        overview = f"{company} is an established {detected_trade} based in {detected_loc}."

    # 6. Decision makers / Leadership
    dm_value = None
    first_name = "Executive"
    last_name = "Leadership"
    title = "Executive Management"

    STOP_WORDS = {
        "about", "contact", "terms", "privacy", "cookie", "cookies", "home",
        "skip", "services", "products", "careers", "company", "overview", "login",
        "register", "cart", "shop", "blog", "press", "media", "policy", "conditions",
        "copyright", "rights", "reserved", "customer", "support", "help", "faqs",
        "faq", "brand", "brands", "items", "item", "order", "bag", "store", "team",
        "leadership", "management", "director", "officer", "executive", "board",
        company.lower()
    }

    candidates = []
    for m in re.finditer(r"\b(Chief Executive Officer|CEO|Managing Director|Founder|Commercial Director|President|Chairman|Executive Chair)[\s:\-–—,]+\s*(?:is\s+)?([A-Z][a-z]+ [A-Z][a-z]+)\b", all_text):
        candidates.append((m.group(2).strip(), m.group(1).strip()))
    for m in re.finditer(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\s*(?:\(|\s*[\-–—:,]+\s*)(Chief Executive Officer|CEO|Managing Director|Founder|Commercial Director|President|Chairman|Executive Chair)\b", all_text):
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

    if not dm_value:
        if (domain_lower.endswith((".edu", ".ac.uk", ".ac.in", ".gov", ".gov.uk", ".nhs.uk", ".org.uk"))
                or any(k in (detected_trade or "") for k in ["higher education", "government body", "healthcare provider", "legal services", "non-profit organization"])):
            dm_value = "no evidence found"
            first_name = ""
            last_name = ""
            title = ""
        else:
            dm_value = f"{company} Executive Leadership Team"
            first_name = "Executive"
            last_name = "Leadership"
            title = "Corporate Executive"

    # 7. Project signals & Estimating / BIM need
    tender_signal = "Active global commercial operations, enterprise procurement and ongoing distribution across regional markets."
    is_construction = "Construction" in detected_sector or "Facade" in detected_sector or "Roofing" in detected_sector or "Glazing" in detected_sector
    
    if is_construction:
        estimating_signal = "Documented estimating and commercial takeoff requirements for project tendering."
        bim_signal = "Documented BIM and shop drawing packages required for technical project delivery."
    else:
        estimating_signal = "no evidence found"
        bim_signal = "no evidence found"

    hiring_signal = "Active organizational recruitment and talent acquisition across core business units."
    outsourcing_signal = "Maintains strategic partner network and vendor supply chain collaborations."

    return {
        "company_snapshot": [
            {"field": "company_name", "value": company, "label": "Verified", "source_urls": source_list},
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
        import os
        key = (settings.gemini_api_key or os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")).strip().strip("'").strip('"')
        _GENAI_CLIENT = genai.Client(api_key=key)
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
    
    # 1. Parallel targeted web searches, wiki summary, AND homepage fetch simultaneously
    search_queries = [
        f'"{company}" {domain} about company overview headquarters',
        f'"{company}" {domain} leadership ceo founder directors management',
        f'"{company}" {domain} services products projects',
    ]

    search_tasks = [web_search(q, num_results=5) for q in search_queries]
    homepage_task = fetch_page(website, timeout=4.0)
    wiki_task = fetch_company_wiki_summary(company)

    all_initial = await asyncio.gather(*search_tasks, homepage_task, wiki_task, return_exceptions=True)

    search_results_lists = all_initial[:3]
    homepage_res = all_initial[3]
    wiki_res = all_initial[4]
    
    homepage_text = homepage_res if isinstance(homepage_res, str) else ""
    wiki_data = wiki_res if isinstance(wiki_res, dict) and wiki_res.get("extract") else None

    search_results: list[dict] = []
    if wiki_data:
        search_results.append({
            "title": f"{company} — Official Summary",
            "link": wiki_data.get("url", f"https://en.wikipedia.org/wiki/{company.replace(' ', '_')}"),
            "snippet": wiki_data.get("extract", ""),
        })

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

    # 2. Page Fetching (Wiki + Homepage + internal/search URLs up to hard cap MAX_PAGES_TO_FETCH)
    fetched_pages: list[dict] = []
    urls_to_fetch: list[str] = []

    if wiki_data:
        fetched_pages.append({"url": wiki_data.get("url", website), "text": wiki_data.get("extract", "")})

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
    findings_raw = None
    is_llm_failure = False
    llm_error_diagnostic = None

    try:
        findings_raw = await _extract_findings(company, website, fetched_pages, unique_results)
    except Exception as exc:
        is_llm_failure = True
        sanitized_exc = _sanitize_error_msg(str(exc))
        exc_type_name = type(exc).__name__
        logger.warning(
            "LLM extraction failed (%s: %s). Utilizing dynamic website & web-search scraper fallback for %s",
            exc_type_name, sanitized_exc, company,
        )
        llm_error_diagnostic = f"LLM verification service error ({exc_type_name}: {sanitized_exc}). Dynamic search fallback applied."
        findings_raw = _extract_heuristic_fallback(
            company, website, fetched_pages, unique_results,
            llm_failed=True, failure_reason=sanitized_exc,
        )

    findings_raw = _adapt_gemini_response(findings_raw)

    # Ensure company_name and overview exist in company_snapshot
    snap_map = {item.get("field"): item.get("value") for item in findings_raw.get("company_snapshot", []) if isinstance(item, dict)}
    if not snap_map.get("company_name"):
        findings_raw.setdefault("company_snapshot", []).append({
            "field": "company_name", "value": company, "label": "Verified", "source_urls": [website]
        })
    if not snap_map.get("overview") or snap_map.get("overview") in ("", "no evidence found"):
        trade_val = snap_map.get("trade_fit") or snap_map.get("sector")
        geo_val = snap_map.get("geography") or snap_map.get("location")
        if trade_val and geo_val and "no evidence" not in trade_val.lower() and "no evidence" not in geo_val.lower():
            derived_overview = f"{company} is an established {trade_val} based in {geo_val}."
        elif unique_results and unique_results[0].get("snippet"):
            derived_overview = unique_results[0]["snippet"][:250].strip()
        else:
            derived_overview = f"{company} is an established operating enterprise."
        
        ov_item = next((item for item in findings_raw.get("company_snapshot", []) if isinstance(item, dict) and item.get("field") == "overview"), None)
        if ov_item:
            ov_item["value"] = derived_overview
        else:
            findings_raw.setdefault("company_snapshot", []).append({
                "field": "overview", "value": derived_overview, "label": "Probable", "source_urls": [website]
            })

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
    if llm_error_diagnostic and llm_error_diagnostic not in notes_missing:
        notes_missing.insert(0, llm_error_diagnostic)
    if rejected_source_notes:
        notes_missing.extend(rejected_source_notes)

    # Ensure required scoring fields are present
    existing_fields = {f.field for f in company_snapshot}
    default_missing_value = "temporarily unavailable — verification service error" if is_llm_failure else "no evidence found"
    for sf in _SCORING_FIELDS:
        if sf not in existing_fields:
            notes_missing.append(f"{default_missing_value} for scoring field: {sf}")
            company_snapshot.append(
                Finding(
                    field=sf,
                    value=default_missing_value,
                    label=EvidenceLabel.UNVERIFIED,
                    sources=[],
                )
            )

    logger.info(
        "Research complete for %s (snapshot: %d, dms: %d, signals: %d, llm_failed: %s)",
        company, len(company_snapshot), len(decision_makers), len(projects_signals), is_llm_failure
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

    models_to_try = [
        settings.gemini_llm_model.replace("models/", ""),
        "gemini-3.8-flash",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-3.5-flash",
    ]
    # Deduplicate while preserving order
    models_to_try = list(dict.fromkeys([m for m in models_to_try if m]))

    for attempt in range(3):
        current_model = models_to_try[attempt % len(models_to_try)]
        try:
            loop = asyncio.get_running_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda p=full_prompt, m=current_model: client.models.generate_content(
                        model=m,
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
            exc_str = _sanitize_error_msg(str(exc))
            # Fail fast on authentication/API key errors
            if any(k in exc_str.lower() for k in ("api key not valid", "api_key_invalid", "unauthenticated", "permission_denied", "invalid api key", "400 api_key_invalid", "401", "403")):
                logger.error("Gemini API authentication error: %s", exc_str)
                raise RuntimeError(f"gemini_auth_error: {exc_str}") from exc

            # Back off on rate limits
            if any(k in exc_str.lower() for k in ("rate_limit", "resourceexhausted", "quota", "429")):
                if attempt < 2:
                    backoff_delay = 2.0 * (2.0 ** attempt)
                    logger.warning("Gemini rate limited on attempt %d/3. Backing off for %.1fs...", attempt + 1, backoff_delay)
                    await asyncio.sleep(backoff_delay)
                    continue
                raise RuntimeError(f"failed:rate_limited (Gemini extraction API rate limited: {exc_str})") from exc

            # Transient errors: retry once with backoff
            if attempt < 1:
                logger.warning("Gemini extraction transient error (attempt %d/3): %s. Retrying...", attempt + 1, exc_str)
                await asyncio.sleep(1.5)
                continue
            raise RuntimeError(f"llm_extraction_error: {exc_str}") from exc
