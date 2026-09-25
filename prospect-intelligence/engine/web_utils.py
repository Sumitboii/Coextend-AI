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

_FETCH_TIMEOUT = 4.0  # seconds per HTTP request (fail fast on dead or slow sites, allows larger homepages)
_SEARCH_TIMEOUT = 8.0  # seconds per Tavily search API call
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
        from tavily import TavilyClient
        _TAVILY_CLIENT = TavilyClient(api_key=settings.tavily_api_key)
    return _TAVILY_CLIENT


def _get_http_client() -> httpx.AsyncClient:
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is None or _HTTPX_CLIENT.is_closed:
        _HTTPX_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(_FETCH_TIMEOUT, connect=1.0),
            follow_redirects=True,
            headers=_BROWSER_HEADERS,
            verify=False,
            limits=httpx.Limits(max_keepalive_connections=30, max_connections=60),
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
            link = urls[i].strip() if i < len(urls) else ""
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
    """Very lightweight HTML -> plain text."""
    html = re.sub(
        r"<(script|style|nav|footer|header|noscript|svg|iframe)[^>]*>.*?</\1>",
        " ",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    html = re.sub(r"<[^>]+>", " ", html)
    html = (
        html.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&nbsp;", " ")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
    )
    html = re.sub(r"\s{2,}", " ", html)
    return html.strip()
