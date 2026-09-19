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

_FETCH_TIMEOUT = 1.5  # seconds per HTTP request (fail fast on dead or slow sites)
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


@retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(0.05),
    reraise=False,
)
async def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Run a web search via Tavily with hard timeout and caching. Returns list of {title, link, snippet} dicts."""
    cache_key = f"{query.strip().lower()}_{num_results}"
    if cache_key in _SEARCH_CACHE:
        logger.debug("Tavily search cache hit for '%s'", query[:60])
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
        logger.debug("Tavily search '%s' -> %d results", query[:80], len(results))
        formatted = [
            {"title": r.get("title", ""), "link": r.get("url", ""), "snippet": r.get("content", "")}
            for r in results
        ]
        _SEARCH_CACHE[cache_key] = formatted
        return formatted
    except asyncio.TimeoutError:
        logger.warning("Tavily search timed out for '%s' after %ds", query[:60], _SEARCH_TIMEOUT)
        return []
    except Exception as exc:
        exc_str = str(exc)
        if any(k in exc_str.lower() for k in ("rate_limit", "quota", "429")):
            logger.error("Tavily rate limit exceeded for query '%s': %s", query[:60], exc)
        else:
            logger.warning("Tavily search failed for '%s': %s", query[:60], exc)
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
