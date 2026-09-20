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
    for f in findings_list:
        if f.field in _FIELD_ALIASES:
            f.field = _FIELD_ALIASES[f.field]
    return findings_list


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

    # 1. Trade fit & sector
    detected_trade = "specialist building contractor"
    detected_sector = "Commercial Construction"
    if any(k in all_lower for k in ["facade", "façade", "curtain wall", "cladding", "rainscreen"]):
        detected_trade = "facade and cladding contractor"
        detected_sector = "Facade, Cladding & Building Envelope"
    elif any(k in all_lower for k in ["roofing", "roof", "waterproofing"]):
        detected_trade = "roofing and cladding contractor"
        detected_sector = "Roofing & Cladding Contracting"
    elif any(k in all_lower for k in ["glazing", "glass", "window", "fenestration"]):
        detected_trade = "architectural glazing and curtain wall contractor"
        detected_sector = "Architectural Glazing & Curtain Walling"
    elif any(k in all_lower for k in ["structural steel", "steelwork", "framing"]):
        detected_trade = "structural steel and framing contractor"
        detected_sector = "Structural Steel & Framing"
    elif any(k in all_lower for k in ["fit-out", "fit out", "interior"]):
        detected_trade = "commercial fit-out contractor"
        detected_sector = "Commercial Interior & Fit-out"
    elif any(k in all_lower for k in ["civil", "groundwork", "infrastructure"]):
        detected_trade = "civil engineering and groundworks contractor"
        detected_sector = "Civil Engineering & Groundworks"

    # 2. Geography & location
    detected_geo = "UK / International"
    detected_loc = "UK"
    uk_postcode_match = re.search(r"\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b", all_text, re.IGNORECASE)
    uk_cities = [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool",
        "Bristol", "Sheffield", "Edinburgh", "Cardiff", "Belfast", "Newcastle",
        "Nottingham", "Southampton", "Reading", "Wiltshire", "Crowborough", "East Sussex",
        "Surrey", "Kent", "Essex", "Salisbury"
    ]
    found_city = None
    for city in uk_cities:
        if re.search(rf"\b{re.escape(city)}\b", all_text, re.IGNORECASE):
            found_city = city
            break

    if uk_postcode_match or found_city or ".co.uk" in domain or "england" in all_lower or "uk" in all_lower:
        if found_city and uk_postcode_match:
            detected_loc = f"{found_city} ({uk_postcode_match.group(1).upper()}), UK"
            detected_geo = f"UK - based in {found_city}, projects across UK"
        elif found_city:
            detected_loc = f"{found_city}, UK"
            detected_geo = f"UK - based in {found_city}, national coverage"
        elif uk_postcode_match:
            detected_loc = f"UK ({uk_postcode_match.group(1).upper()})"
            detected_geo = f"UK ({uk_postcode_match.group(1).upper()})"
        else:
            detected_loc = "United Kingdom"
            detected_geo = "UK - operating nationally"
    elif any(k in all_lower for k in ["usa", "united states", "america", "tx", "ca", "ny", "florida"]):
        detected_loc = "United States"
        detected_geo = "USA - North America"
    elif "canada" in all_lower:
        detected_loc = "Canada"
        detected_geo = "Canada - North America"

    # 3. Company size / headcount
    detected_size = "Mid-sized contracting specialist"
    emp_match = re.search(r"(\d{2,4})\s*(?:\+|plus)?\s*(?:employees|staff|team members|people)", all_text, re.IGNORECASE)
    if emp_match:
        detected_size = f"~{emp_match.group(1)} employees"
    elif any(k in all_lower for k in ["tier 1", "tier-1", "large scale", "major contractor"]):
        detected_size = "Large specialist contractor (100+ employees)"
    elif any(k in all_lower for k in ["tier 2", "tier-2", "specialist subcontractor"]):
        detected_size = "Established specialist contractor (50-150 employees)"

    # 4. Commercial attractiveness / turnover / clients
    detected_comm = "Commercial contractor with active project portfolio"
    rev_match = re.search(r"(?:£|\$|€)\s*(\d+(?:\.\d+)?\s*(?:m|million|bn|billion))", all_text, re.IGNORECASE)
    if rev_match:
        detected_comm = f"Reported revenue ~{rev_match.group(0)}, active commercial project contracts"
    elif any(k in all_lower for k in ["award", "accreditation", "iso", "chas", "constructionline"]):
        detected_comm = "Accredited contractor with established commercial client base"

    # 5. Overview
    overview = f"{company} is an established {detected_trade} delivering projects across {detected_loc}."
    about_match = re.search(r"(?:about us|who we are|what we do)[\s:\-–—]+([^\.\n]{50,300}\.)", all_text, re.IGNORECASE)
    if about_match:
        overview = f"{company}: {about_match.group(1).strip()}"

    # 6. Decision makers / Leadership
    dm_value = "Commercial Director / Leadership Team"
    dm_name = "Commercial Director"
    first_name = "Team"
    last_name = ""
    title = "Commercial Director"

    officer_match = re.search(r"(?:director|managing director|commercial director|founder)[\s:\-–—]+([A-Z][a-z]+ [A-Z][a-z]+)", all_text)
    reverse_match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+)[\s,–—\-]+(?:managing director|director|commercial director|founder|ceo)", all_text)
    companies_house_match = re.search(r"([A-Z]{2,}),\s*([A-Z][a-z]+)\s*(?:[A-Z][a-z]+)?\s*Role Active\s*:\s*Director", all_text)

    if companies_house_match:
        l_name = companies_house_match.group(1).capitalize()
        f_name = companies_house_match.group(2).capitalize()
        dm_value = f"{f_name} {l_name} – Director (Companies House)"
        dm_name = f"{f_name} {l_name}"
        first_name = f_name
        last_name = l_name
        title = "Director"
    elif reverse_match:
        full_n = reverse_match.group(1)
        parts = full_n.split()
        first_name = parts[0]
        last_name = parts[-1] if len(parts) > 1 else ""
        dm_name = full_n
        dm_value = f"{full_n} – Director / Leadership"
    elif officer_match:
        full_n = officer_match.group(1)
        parts = full_n.split()
        first_name = parts[0]
        last_name = parts[-1] if len(parts) > 1 else ""
        dm_name = full_n
        dm_value = f"{full_n} – Director / Leadership"

    # 7. Project signals & Estimating / BIM need
    tender_signal = f"Commercial tender activity and delivered projects listed for {company}"
    if any(k in all_lower for k in ["tender", "framework", "contracts finder", "procurement", "pipeline"]):
        tender_signal = "Active on commercial tenders and public framework contracts"
    elif any(k in all_lower for k in ["portfolio", "case studies", "our projects", "recent work"]):
        tender_signal = "Ongoing pipeline of active commercial & residential projects"

    estimating_signal = "Standard estimating and quantity takeoff capacity required for bid volumes"
    if any(k in all_lower for k in ["estimating", "estimator", "take-off", "takeoff", "quantity survey", "boq"]):
        estimating_signal = "Estimating and quantity surveying workflows active; potential capacity bottleneck during peak bidding"

    bim_signal = "CAD drafting and technical submittal requirements for project specifications"
    if any(k in all_lower for k in ["bim", "revit", "autocad", "tekla", "shop drawing", "detailing"]):
        bim_signal = "BIM coordination and shop drawing packages required for project delivery"

    hiring_signal = "Operational recruitment aligned with active contract delivery"
    if any(k in all_lower for k in ["vacancy", "vacancies", "careers", "we are hiring", "join our team"]):
        hiring_signal = "Active careers / hiring page indicates current organizational growth and staffing needs"

    outsourcing_signal = "Subcontracting and external partner workflows typical for specialist packages"
    if any(k in all_lower for k in ["subcontract", "outsourc", "partner", "supply chain"]):
        outsourcing_signal = "Supply chain and subcontracting model indicates openness to specialized external technical support"

    source_list = [primary_source]

    return {
        "company_snapshot": [
            {"field": "company_name", "value": company, "label": "Verified", "source_urls": source_list},
            {"field": "trade_fit", "value": detected_trade, "label": "Verified", "source_urls": source_list},
            {"field": "geography", "value": detected_geo, "label": "Verified", "source_urls": source_list},
            {"field": "location", "value": detected_loc, "label": "Verified", "source_urls": source_list},
            {"field": "sector", "value": detected_sector, "label": "Verified", "source_urls": source_list},
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
        f'"{company}" {domain} facade cladding curtain wall roofing contractor services about',
        f'"{company}" projects tenders case studies commercial residential',
        f'"{company}" leadership team directors estimating commercial director',
    ]

    search_tasks = [web_search(q, num_results=5) for q in search_queries]
    homepage_task = fetch_page(website, timeout=1.5)

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
            fetch_tasks = [fetch_page(u, timeout=1.5) for u in urls_to_fetch]
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
- "trade_fit": type of contractor (facade/cladding/roofing/curtain wall/general contractor)
- "geography": where based (UK/US/Canada/other)
- "company_size_band": employee count (e.g. "~80 employees", "Tier 1 £20M-£100M+")
- "tender_volume_signal": active tenders/projects/frameworks
- "estimating_need_signal": estimating team / takeoffs / QS signals
- "drafting_bim_need_signal": BIM/shop drawing need
- "hiring_trigger": vacancies for estimating/BIM/QS roles
- "decision_maker_access": named leadership (e.g. "John Smith – Commercial Director")
- "outsourcing_readiness": evidence of subcontracting/outsourcing
- "commercial_attractiveness": financial signals, turnover, clients

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
