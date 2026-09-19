"""
Source Verification Engine.
Validates that search results and fetched pages actually belong to the searched company.
Prevents pulling in data from similarly-named companies, demos, or unrelated sources.
"""
from __future__ import annotations

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

from engine.web_utils import fetch_page

logger = logging.getLogger(__name__)


class SourceVerification:
    """Verifies sources match the searched company."""
    
    # Similarity threshold: company name must match 70%+ with fetched page content
    COMPANY_NAME_MATCH_THRESHOLD = 0.70
    
    # Keywords that indicate a real company page vs. demo/placeholder
    DEMO_KEYWORDS = [
        "sample", "template", "example", "demo", "placeholder", "test",
        "coming soon", "under construction", "staging", "pre-launch",
        "[your", "[company", "(replace with", "< insert"
    ]
    
    # Domains that are known to host directories/listings (often misleading matches)
    DIRECTORY_DOMAINS = [
        "yellowpages.com", "google.com/maps", "maps.google.com", "yelp.com", "crunchbase.com",
        "linkedin.com/company", "indeed.com", "glassdoor.com", "buildr.co.uk",
        "thumbs.com", "ratemyapprenticeship.co.uk", "trustmark.org.uk"
    ]
    
    # Keywords that indicate a company page is genuine
    COMPANY_CREDIBILITY_KEYWORDS = {
        "company_description": ["we are", "we specialize", "our mission", "established",
                                "based in", "founded", "headquarters", "about us", "specialists", "contractor"],
        "contact_info": ["contact us", "contact", "phone", "email", "address", "office",
                        "head office", "registered office", "located"],
        "services": ["our services", "services", "what we do", "solutions", "capabilities",
                    "services offered", "products", "specializes in", "specialize"],
        "experience": ["years of experience", "established", "since", "founded in",
                      "over", "decades", "years"]
    }
    
    # Patterns to extract company name from pages
    COMPANY_NAME_PATTERNS = [
        r"(?:Company|About Us).*?<h1[^>]*>([^<]+)</h1>",  # H1 after "Company" section
        r"(?:© |Copyright ©?\s*)(\d{4}\s+)?([^<|–\n]+)",   # Copyright line
        r"(?:Welcome to|About|We Are)\s+([^<|,;.?!]+)",    # "Welcome to X" / "About X"
    ]

    @classmethod
    async def verify_homepage(cls, company_name: str, website: str, page_text: str) -> tuple[bool, Optional[str]]:
        """
        Verify homepage matches the submitted company.
        
        Returns: (is_verified, reason)
        - (True, None) if homepage matches
        - (False, reason) if verification failed
        """
        if not page_text or not page_text.strip():
            return False, "Homepage fetch failed or returned empty"
        
        page_lower = page_text.lower()
        
        # 1. Check for demo/placeholder content
        demo_found = [kw for kw in cls.DEMO_KEYWORDS if kw in page_lower]
        if demo_found:
            return False, f"Homepage appears to be demo/placeholder (found: {', '.join(demo_found[:2])})"
        
        # 2. Extract company name from page and compare
        company_name_normalized = cls._normalize_company_name(company_name)
        page_company_names = [cls._normalize_company_name(pn) for pn in cls._extract_company_names_from_page(page_text)]
        
        name_found = (
            company_name_normalized in page_lower
            or any(company_name_normalized in pn or pn.startswith(company_name_normalized) for pn in page_company_names)
        )
        
        best_match = max(
            [SequenceMatcher(None, company_name_normalized, pn).ratio() for pn in page_company_names],
            default=0
        )
        
        if not name_found and best_match < cls.COMPANY_NAME_MATCH_THRESHOLD:
            extracted = page_company_names[:2] if page_company_names else ["(none found)"]
            return False, f"Company name mismatch. Expected '{company_name}', page mentions: {extracted}"
        
        # 3. Check for credibility signals (company description, contact info, etc.)
        credibility_score = 0
        for category, keywords in cls.COMPANY_CREDIBILITY_KEYWORDS.items():
            if any(kw in page_lower for kw in keywords):
                credibility_score += 1
        
        if credibility_score < 1:
            return False, "Homepage lacks credibility signals (no company description or contact info found)"
        
        return True, None

    @classmethod
    async def verify_source_url(cls, company_name: str, source_url: str, page_text: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        Verify a source URL (from search results) actually mentions the searched company.
        
        Returns: (is_verified, reason)
        """
        if not source_url or not source_url.startswith(("http://", "https://")):
            return False, "Invalid URL format"
        
        # 1. Check if it's a known directory/listing domain
        domain_match = [d for d in cls.DIRECTORY_DOMAINS if d in source_url.lower()]
        if domain_match:
            return False, f"URL is from directory/listing site ({domain_match[0]}), not reliable company source"
        
        # 2. Fetch page if not provided
        if page_text is None:
            page_text = await fetch_page(source_url, timeout=1.5)
        
        if not page_text or not page_text.strip():
            return False, "Could not fetch source page"
        
        # 3. Check for company name mention
        company_name_normalized = cls._normalize_company_name(company_name)
        page_lower = page_text.lower()
        
        # Exact match (case-insensitive)
        if company_name_normalized in page_lower:
            return True, None
        
        # Fuzzy match for variations (Ltd/Ltd., Inc, LLC, etc.)
        extracted_companies = cls._extract_company_names_from_page(page_text)
        best_match = max(
            [SequenceMatcher(None, company_name_normalized, ec).ratio() for ec in extracted_companies],
            default=0
        )
        
        if best_match >= cls.COMPANY_NAME_MATCH_THRESHOLD:
            return True, None
        
        return False, f"Source page does not mention '{company_name}'"

    @staticmethod
    def _normalize_company_name(name: str) -> str:
        """Normalize company name for comparison."""
        name = name.lower().strip()
        for suffix in [" ltd", " ltd.", " limited", " plc", " inc", " inc.", " llc", " corp", " corporation"]:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
        name = re.sub(r"\s+", " ", name)
        return name

    @staticmethod
    def _extract_company_names_from_page(page_text: str) -> list[str]:
        """Extract likely company names from page content."""
        names = set()
        for pattern in SourceVerification.COMPANY_NAME_PATTERNS:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = next((m for m in match if m), None)
                if match and len(match) > 2 and len(match) < 150:
                    match = re.sub(r"[<>\"']", "", match).strip()
                    if match and not match.startswith(("http", "www", "©", "2")):
                        names.add(match)
        h_tags = re.findall(r"<h[12][^>]*>([^<]+)</h[12]>", page_text, re.IGNORECASE)
        for tag in h_tags:
            tag_clean = tag.strip()
            if len(tag_clean) > 2 and len(tag_clean) < 150 and not any(c in tag_clean.lower() for c in ["http", "www"]):
                names.add(tag_clean)
        return list(names)

    @classmethod
    async def verify_all_sources(
        cls,
        company_name: str,
        website: str,
        fetched_pages: list[dict],
        search_results: list[dict],
    ) -> tuple[list[dict], list[str]]:
        """Verify all fetched pages and search results."""
        verified_pages = []
        rejected_sources = []
        
        # Verify homepage first
        homepage_page = next((p for p in fetched_pages if p["url"] == website), None)
        if homepage_page:
            is_verified, reason = await cls.verify_homepage(company_name, website, homepage_page["text"])
            if not is_verified:
                rejected_sources.append(f"Homepage: {reason}")
                logger.warning("Homepage verification failed for %s: %s", company_name, reason)
            verified_pages.append({
                **homepage_page,
                "verified": is_verified,
                "reason": reason or "Homepage matches company"
            })
        
        # Verify other fetched pages
        for page in fetched_pages:
            if page["url"] == website:
                continue
            
            is_verified, reason = await cls.verify_source_url(company_name, page["url"], page["text"])
            if not is_verified:
                rejected_sources.append(f"{page['url']}: {reason}")
            
            verified_pages.append({
                **page,
                "verified": is_verified,
                "reason": reason or "Source verified"
            })
        
        # Verify search result URLs
        for result in search_results:
            url = result.get("link", "")
            title = result.get("title", "")
            snippet = result.get("snippet", "")
            
            company_norm = cls._normalize_company_name(company_name)
            search_text_lower = (title + " " + snippet).lower()
            
            if company_norm in search_text_lower:
                verified_pages.append({
                    "url": url,
                    "text": snippet,
                    "verified": True,
                    "reason": "Company name found in search result"
                })
            else:
                domain_match = [d for d in cls.DIRECTORY_DOMAINS if d in url.lower()]
                if domain_match:
                    rejected_sources.append(f"Search result {url}: Directory/listing site ({domain_match[0]})")
                else:
                    rejected_sources.append(f"Search result {url}: Company name not mentioned in title/snippet")
        
        return verified_pages, rejected_sources

    @staticmethod
    def build_sources_rejected_note(rejected_sources: list[str]) -> list[str]:
        """Convert rejected sources into notes_missing entries."""
        if not rejected_sources:
            return []
        notes = ["Sources rejected due to company verification:"]
        for reason in rejected_sources[:10]:
            notes.append(f"  - {reason}")
        if len(rejected_sources) > 10:
            notes.append(f"  ... and {len(rejected_sources) - 10} more sources rejected")
        return notes


# Module-level function aliases for backward compatibility
verify_homepage = SourceVerification.verify_homepage
verify_source_url = SourceVerification.verify_source_url
verify_all_sources = SourceVerification.verify_all_sources
build_sources_rejected_note = SourceVerification.build_sources_rejected_note
