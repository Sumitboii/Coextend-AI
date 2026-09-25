"""
Web search and page-fetch utilities.
Optimized for high-speed, parallel asynchronous research with connection pooling and hard timeouts.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 2.5  # fast fail per HTTP request to eliminate lag
_SEARCH_TIMEOUT = 5.0  # seconds per Tavily search API call
_MAX_PAGE_CHARS = 8_000  # truncate very large pages to keep context clean

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Upgrade-Insecure-Requests": "1",
}


_SEARCH_CACHE: dict[str, list[dict]] = {}
_PAGE_CACHE: dict[str, str] = {}
_TAVILY_CLIENT = None
_HTTPX_CLIENT: httpx.AsyncClient | None = None


def _get_tavily_client():
    global _TAVILY_CLIENT
    if _TAVILY_CLIENT is None:
        import os
        from tavily import TavilyClient
        key = (settings.tavily_api_key or os.environ.get("TAVILY_API_KEY", "") or os.environ.get("TAVILY_KEY", "")).strip().strip("'").strip('"')
        _TAVILY_CLIENT = TavilyClient(api_key=key)
    return _TAVILY_CLIENT


def _get_http_client() -> httpx.AsyncClient:
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is None or _HTTPX_CLIENT.is_closed:
        _HTTPX_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(_FETCH_TIMEOUT, connect=1.0),
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
            verify=False,
            limits=httpx.Limits(max_keepalive_connections=40, max_connections=80),
        )
    return _HTTPX_CLIENT


_JS_SHELL_PATTERNS = [
    re.compile(r'id=["\'](?:root|__next|app|__nuxt|main-app|app-root)["\']', re.IGNORECASE),
    re.compile(r'<div[^>]+id=["\'](?:root|__next|app)["\']', re.IGNORECASE),
    re.compile(r'<(?:app-root|next-app|nuxt-app)>', re.IGNORECASE),
]


def is_js_shell(html: str, text: str) -> bool:
    """
    Detect if fetched HTML is mostly an empty JS shell / SPA without server-rendered content.
    Returns True if:
      - Raw HTML contains telltale root containers (<div id="root">, etc.) AND extracted text is short (<300 chars)
      - Raw HTML is substantial (>1200 chars) but stripped text is extremely sparse (<150 chars)
      - Text contains common SPA noscript warnings ("enable JavaScript to run this app")
    """
    if not html:
        return True
    t_clean = text.strip().lower()
    if len(t_clean) < 40:
        return True
    if any(p.search(html) for p in _JS_SHELL_PATTERNS) and len(t_clean) < 350:
        return True
    if len(html) > 1200 and len(t_clean) < 180:
        return True
    if any(k in t_clean for k in ["you need to enable javascript", "enable javascript to run this app", "javascript is required"]):
        return True
    return False


import html as html_lib


async def fetch_company_wiki_summary(company_name: str) -> dict | None:
    """
    Fetch authoritative, structured company background summary from Wikipedia REST API.
    Zero API key required; provides verified HQ location, sector, and overview for global entities.
    Automatically leverages NLP typo suggestions if exact name isn't found.
    """
    import unicodedata
    clean_name = unicodedata.normalize('NFKD', company_name).encode('ASCII', 'ignore').decode('utf-8').strip()
    candidates = [
        company_name.strip(),
        clean_name,
        f"{clean_name}, Inc.",
        f"{clean_name} Corporation",
        f"{clean_name} Video Communications" if "zoom" in clean_name.lower() else "",
        f"{clean_name} S.A." if "nestle" in clean_name.lower() else "",
    ]
    candidates = [c for c in candidates if c]

    client = _get_http_client()
    for cand in candidates:
        title = cand.replace(" ", "_").replace("&", "%26")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
        try:
            r = await client.get(url, timeout=2.5)
            if r.status_code == 200:
                data = r.json()
                if data.get("type") in ("standard", "") and data.get("extract"):
                    wiki_url = data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{title}")
                    return {
                        "title": data.get("title", company_name),
                        "extract": data.get("extract", ""),
                        "description": data.get("description", ""),
                        "url": wiki_url,
                    }
        except Exception:
            continue

    # Fallback to NLP OpenSearch suggestions
    try:
        from engine.nlp_resolver import fetch_nlp_typo_suggestions
        suggs = await fetch_nlp_typo_suggestions(company_name)
        for s in suggs:
            title = s.replace(" ", "_").replace("&", "%26")
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
            r = await client.get(url, timeout=2.5)
            if r.status_code == 200:
                data = r.json()
                if data.get("type") in ("standard", "") and data.get("extract"):
                    wiki_url = data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{title}")
                    return {
                        "title": data.get("title", s),
                        "extract": data.get("extract", ""),
                        "description": data.get("description", ""),
                        "url": wiki_url,
                    }
    except Exception:
        pass

    return None


@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(0.05),
    reraise=False,
)
async def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Run a web search via Tavily with hard timeout and caching. Falls back to DuckDuckGo HTML search."""
    cache_key = f"{query.strip().lower()}_{num_results}"
    if cache_key in _SEARCH_CACHE:
        logger.debug("Search cache hit for '%s'", query[:60])
        return _SEARCH_CACHE[cache_key]

    def _search():
        client = _get_tavily_client()
        return client.search(query=query, max_results=num_results, search_depth="basic")

    loop = asyncio.get_running_loop()
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(None, _search),
            timeout=_SEARCH_TIMEOUT,
        )
        results = response.get("results", [])
        formatted = [
            {"title": r.get("title", ""), "link": r.get("url", ""), "snippet": r.get("content", "")}
            for r in results
        ]
        if formatted:
            logger.info("Search path [Tavily] used for %r: %d results retrieved", query[:80], len(formatted))
            _SEARCH_CACHE[cache_key] = formatted
            return formatted
    except asyncio.TimeoutError:
        logger.warning("Tavily search timed out for '%s' after %ds", query[:60], _SEARCH_TIMEOUT)
    except Exception as exc:
        exc_str = str(exc)
        if any(k in exc_str.lower() for k in ("rate_limit", "quota", "429")):
            logger.error("Tavily rate limit exceeded for query '%s': %s", query[:60], exc)
        else:
            logger.warning("Tavily search failed for '%s': %s", query[:60], exc)

    # Fallback: DuckDuckGo HTML search (no API key required)
    try:
        ddg_results = await _ddg_search_fallback(query, num_results)
        if ddg_results:
            logger.info("Search path [DuckDuckGo fallback] used for %r: %d results retrieved", query[:80], len(ddg_results))
            _SEARCH_CACHE[cache_key] = ddg_results
            return ddg_results
        logger.warning("DuckDuckGo fallback search returned 0 results for %r", query[:80])
    except Exception as ddg_exc:
        logger.warning("DuckDuckGo fallback search exception for '%s': %s", query[:60], ddg_exc)

    return []


async def _ddg_search_fallback(query: str, num_results: int = 5) -> list[dict]:
    """Resilient fallback search via DuckDuckGo HTML when Tavily is rate-limited or unconfigured."""
    try:
        client = _get_http_client()
        resp = await client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            timeout=4.0,
        )
        if resp.status_code != 200:
            logger.warning(
                "DuckDuckGo search returned HTTP status %d for query %r (body preview: %r)",
                resp.status_code, query[:80], resp.text[:150],
            )
            return []
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
        urls = re.findall(r'<a class="result__url"[^>]*href="([^"]*)"', resp.text)
        out = []
        for i, s in enumerate(snippets[:num_results]):
            clean = re.sub(r'<[^>]+>', '', s).strip()
            clean = html_lib.unescape(clean)
            link = urls[i].strip() if i < len(urls) else ""
            if link.startswith("//"):
                link = "https:" + link
            if clean:
                out.append({"title": f"Web Result {i+1}", "link": link, "snippet": clean})
        return out
    except Exception as exc:
        logger.warning("DuckDuckGo HTTP request failed for %r: %s", query[:80], exc)
        return []


@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(0.05),
    reraise=False,
)
async def fetch_page(url: str, timeout: float = _FETCH_TIMEOUT) -> str:
    """
    Fetch a URL asynchronously and return its stripped text content.
    Fails fast without blocking the pipeline.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""
    if url in _PAGE_CACHE:
        return _PAGE_CACHE[url]
    try:
        client = _get_http_client()
        response = await client.get(url, timeout=timeout)
        if response.status_code != 200:
            logger.debug("Fetch %s returned status %d", url, response.status_code)
            return ""
        html = response.text
        text = _html_to_text(html)
        if is_js_shell(html, text):
            logger.info("Page %s detected as JS/SPA shell (text=%d chars, html=%d chars). Snippets will be prioritized.", url, len(text), len(html))
        if len(text) > _MAX_PAGE_CHARS:
            text = text[:_MAX_PAGE_CHARS] + "\n[TRUNCATED]"
        _PAGE_CACHE[url] = text
        return text
    except Exception as exc:
        logger.debug("Fetch failed for %s: %s", url, exc)
        return ""


def _html_to_text(html: str) -> str:
    """Lightweight HTML -> plain text with rich metadata extraction."""
    meta_parts = []
    # Extract page title
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if title_m:
        title_text = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
        if title_text:
            meta_parts.append(title_text)

    # Extract meta descriptions and og:description
    for m in re.finditer(r'<meta[^>]+(?:name|property)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE):
        k, v = m.group(1).lower(), m.group(2).strip()
        if any(target in k for target in ("description", "og:description", "twitter:description", "keywords", "og:title")):
            if len(v) > 20 and v not in meta_parts:
                meta_parts.append(v)
    
    # Strip heavy tags
    body_clean = re.sub(
        r"<(script|style|nav|footer|header|noscript|svg|iframe)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    body_clean = re.sub(r"<[^>]+>", " ", body_clean)
    
    combined = " ".join(meta_parts) + " " + body_clean
    combined = html_lib.unescape(combined)
    combined = re.sub(r"\s{2,}", " ", combined)
    return combined.strip()


def extract_company_channels_and_links(
    html: str,
    website: str,
    company_name: str = "",
    snippets: list[dict] | None = None,
) -> dict[str, str]:
    """
    Extract direct contact channels, LinkedIn profile/company URLs, About Us,
    and Contact Us pages from HTML and search snippets.
    """
    from urllib.parse import urljoin, urlparse
    import unicodedata

    results: dict[str, str] = {}
    snippets = snippets or []

    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]
    base_clean = f"https://{domain}" if not website.startswith(("http://", "https://")) else website

    # 1. LinkedIn Extraction (Company Page & Decision-Maker Profile)
    linkedin_matches = re.findall(
        r'https?://(?:www\.)?linkedin\.com/(?:company|school)/([a-zA-Z0-9_\-\.\%]+)',
        html,
        re.IGNORECASE,
    )
    if linkedin_matches:
        results["linkedin_url"] = f"https://www.linkedin.com/company/{linkedin_matches[0].strip('/')}"

    # Check search snippets for LinkedIn company URL if not found in HTML
    if "linkedin_url" not in results:
        for s in snippets:
            link = s.get("link", "")
            m = re.search(r'https?://(?:www\.)?linkedin\.com/(?:company|school)/([a-zA-Z0-9_\-\.\%]+)', link, re.IGNORECASE)
            if m:
                results["linkedin_url"] = f"https://www.linkedin.com/company/{m.group(1).strip('/')}"
                break

    # Decision-maker LinkedIn profile
    dm_li_matches = re.findall(
        r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_\-\.\%]+)',
        html,
        re.IGNORECASE,
    )
    if dm_li_matches:
        results["decision_maker_linkedin"] = f"https://www.linkedin.com/in/{dm_li_matches[0].strip('/')}"
    else:
        for s in snippets:
            link = s.get("link", "")
            m = re.search(r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9_\-\.\%]+)', link, re.IGNORECASE)
            if m:
                results["decision_maker_linkedin"] = f"https://www.linkedin.com/in/{m.group(1).strip('/')}"
                break

    # Fallback company LinkedIn if still not found
    if "linkedin_url" not in results and company_name:
        clean_slug = re.sub(r'[^a-zA-Z0-9]+', '-', company_name.strip().lower()).strip('-')
        if clean_slug:
            results["linkedin_url"] = f"https://www.linkedin.com/company/{clean_slug}"

    # 2. About Us URL Extraction
    about_hrefs = re.findall(
        r'href=["\']([^"\']*(?:about|about-us|who-we-are|our-story|our-company|company)[^"\']*)["\']',
        html,
        re.IGNORECASE,
    )
    valid_about = [
        urljoin(base_clean, h)
        for h in about_hrefs
        if not any(h.lower().endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.svg', '.zip'))
        and urlparse(urljoin(base_clean, h)).netloc == domain
    ]
    if valid_about:
        results["about_us_url"] = valid_about[0]
    else:
        # Check snippets for about link
        for s in snippets:
            link = s.get("link", "")
            if domain in link and any(k in link.lower() for k in ["/about", "/who-we-are", "/company", "/story"]):
                results["about_us_url"] = link
                break
        if "about_us_url" not in results:
            results["about_us_url"] = urljoin(base_clean, "/about")

    # 3. Contact Us URL Extraction
    contact_hrefs = re.findall(
        r'href=["\']([^"\']*(?:contact|contact-us|get-in-touch|reach-us|support|enquiries)[^"\']*)["\']',
        html,
        re.IGNORECASE,
    )
    valid_contact = [
        urljoin(base_clean, h)
        for h in contact_hrefs
        if not any(h.lower().endswith(ext) for ext in ('.pdf', '.jpg', '.png', '.svg', '.zip'))
        and urlparse(urljoin(base_clean, h)).netloc == domain
    ]
    if valid_contact:
        results["contact_us_url"] = valid_contact[0]
    else:
        for s in snippets:
            link = s.get("link", "")
            if domain in link and any(k in link.lower() for k in ["/contact", "/get-in-touch", "/reach-us", "/enquiry"]):
                results["contact_us_url"] = link
                break
        if "contact_us_url" not in results:
            results["contact_us_url"] = urljoin(base_clean, "/contact")

    # 4. Email Extraction
    mailto_matches = re.findall(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', html, re.IGNORECASE)
    valid_emails = [
        e for e in mailto_matches
        if not any(e.lower().endswith(ext) for ext in ('.png', '.jpg', '.webp', '.gif'))
        and not any(k in e.lower() for k in ['sentry', 'wixpress', 'example', 'domain.com', 'user@'])
    ]
    if valid_emails:
        results["contact_email"] = valid_emails[0]
    else:
        # Text regex email
        raw_emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@(?:' + re.escape(domain) + r'|[a-zA-Z0-9-]+\.[a-zA-Z]{2,})\b', html)
        filtered_raw = [
            e for e in raw_emails
            if not any(e.lower().endswith(ext) for ext in ('.png', '.jpg', '.webp', '.gif', '.svg'))
            and not any(k in e.lower() for k in ['sentry', 'wixpress', 'example', 'domain.com', 'user@'])
            and any(k in e.lower() for k in ['info', 'contact', 'hello', 'enquiries', 'support', 'sales', 'press', 'media'])
        ]
        if filtered_raw:
            results["contact_email"] = filtered_raw[0]

    # 5. Phone Number Extraction
    tel_matches = re.findall(r'tel:([+0-9\s\(\)\-]{7,25})', html, re.IGNORECASE)
    if tel_matches:
        clean_tel = re.sub(r'[^\+0-9\s\(\)\-]', '', tel_matches[0]).strip()
        if len(clean_tel) >= 7:
            results["contact_phone"] = clean_tel

    return results

