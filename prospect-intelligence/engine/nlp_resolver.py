"""
NLP Entity Resolver & Typo-Tolerance Engine for Prospect Intelligence.
Automatically detects, corrects, and normalizes misspelled company names,
imperfect domains, and malformed URLs so queries always resolve accurately.
"""
from __future__ import annotations

import asyncio
import logging
import re
import unicodedata
from urllib.parse import urlparse, urljoin
import httpx

from config import settings

logger = logging.getLogger(__name__)

_HTTP_HEADERS = {
    "User-Agent": "CoextendAI-NLP/1.0 (https://coextend.ai; contact@coextend.ai)",
    "Accept": "application/json,text/html,*/*",
}

# Common TLD typos
_TLD_TYPOS = {
    ".con": ".com",
    ".cmo": ".com",
    ".c0m": ".com",
    ".comm": ".com",
    ".ogr": ".org",
    ".og": ".org",
    ".neet": ".net",
    ".nt": ".net",
    ".c0": ".co",
}

# Common corporate legal suffix variations to normalize for fuzzy matching
_LEGAL_SUFFIXES = [
    r"\b(?:ltd|limited|inc|incorporated|corp|corporation|llc|llp|plc|sa|s\.a\.|gmbh|nv|n\.v\.|pvt|private limited|co\.?|company)\b"
]


def clean_url(raw_url: str) -> str:
    """
    Sanitize and canonicalize any user-entered website string.
    Fixes missing schemes, typos in http, spaces, and common TLD errors.
    """
    if not raw_url:
        return ""
    u = str(raw_url).strip()
    
    # Fix common protocol typos
    u = re.sub(r'^(?:https?[\/\:\s]+|htp[\:\/]+|htps[\:\/]+|https?[\:\/]+)', 'https://', u, flags=re.IGNORECASE)
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    
    # Fix TLD typos
    for typo, fix in _TLD_TYPOS.items():
        if u.lower().endswith(typo) or f"{typo}/" in u.lower():
            u = re.sub(re.escape(typo) + r'(\/|$)', fix + r'\1', u, flags=re.IGNORECASE)
            break
            
    # Remove unwanted trailing characters
    u = u.strip().rstrip('.,;:)]>')
    return u


def normalize_company_name(name: str) -> str:
    """Normalize whitespace, accents, and punctuation in company names."""
    if not name:
        return ""
    # Strip excessive punctuation and whitespace
    n = unicodedata.normalize('NFKD', name)
    n = re.sub(r'[\t\r\n]+', ' ', n)
    n = re.sub(r'\s{2,}', ' ', n)
    return n.strip()


async def fetch_nlp_typo_suggestions(company_name: str) -> list[str]:
    """
    Query Wikipedia OpenSearch API to fetch real, authoritative entity
    corrections for misspelled or typo-laden company names.
    Fast (typically <200ms) and zero API key dependency.
    """
    cleaned = normalize_company_name(company_name)
    if not cleaned or len(cleaned) < 2:
        return []
        
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "opensearch",
        "search": cleaned,
        "limit": "4",
        "namespace": "0",
        "format": "json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=2.5, headers=_HTTP_HEADERS) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if len(data) > 1 and isinstance(data[1], list):
                    suggestions = [str(s).strip() for s in data[1] if s]
                    return suggestions
    except Exception as exc:
        logger.debug("NLP OpenSearch lookup error for %r: %s", company_name, exc)
        
    return []


def _levenshtein_distance(s1: str, s2: str) -> int:
    """Compute standard Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def find_best_entity_match(input_name: str, candidates: list[str]) -> str | None:
    """
    Find the best matched entity from candidates using token overlap & edit distance.
    Returns the corrected canonical name if confidence is high.
    """
    if not candidates:
        return None
        
    norm_input = normalize_company_name(input_name).lower()
    input_tokens = set(re.findall(r'\w+', norm_input))
    
    # Strip artistic / non-business suffixes (e.g. (opera), (film), (album), (song), (novel), (character))
    media_pattern = r'\b(?:\(opera\)|\(film\)|\(album\)|\(song\)|\(novel\)|\(character\)|\(soundtrack\)|\(play\))\b'
    product_terms = r'\b(?:exchange|photoshop|flash|windows|office|suite|cloud|silicon|reader|acrobat|tower|center)\b'
    
    cleaned_candidates = []
    for cand in candidates:
        cand_clean = cand
        if re.search(media_pattern, cand, flags=re.IGNORECASE):
            # Prefer business candidate if present, avoid artistic media
            continue
        # If candidate has product suffix, clean it
        cand_sub = re.sub(product_terms, '', cand, flags=re.IGNORECASE).strip()
        if cand_sub and len(cand_sub) >= 3:
            cleaned_candidates.append(cand_sub)
        cleaned_candidates.append(cand)
        
    if not cleaned_candidates:
        cleaned_candidates = candidates
        
    best_candidate = None
    best_score = float('inf')
    
    for cand in cleaned_candidates:
        norm_cand = normalize_company_name(cand).lower()
        # Strip legal suffix from candidate for fair comparison
        cand_clean = norm_cand
        for pat in _LEGAL_SUFFIXES:
            cand_clean = re.sub(pat, '', cand_clean, flags=re.IGNORECASE).strip()
            
        cand_tokens = set(re.findall(r'\w+', cand_clean))
        
        # Exact token match or candidate is clean single word matching input
        if input_tokens and cand_tokens and (input_tokens == cand_tokens or cand_clean == norm_input):
            return cand
            
        dist = _levenshtein_distance(norm_input, cand_clean)
        max_len = max(len(norm_input), len(cand_clean), 1)
        rel_dist = dist / max_len
        
        # If relative edit distance <= 0.40, high confidence match
        if rel_dist < best_score and rel_dist <= 0.40:
            best_score = rel_dist
            best_candidate = cand
            
    return best_candidate


async def resolve_company_entity(
    company_name: str,
    website: str,
) -> tuple[str, str, dict]:
    """
    Full NLP entity resolution and typo correction pipeline.
    
    Returns:
      (canonical_company_name, canonical_website, metadata_dict)
    """
    clean_name = normalize_company_name(company_name)
    canonical_url = clean_url(website)
    
    meta: dict[str, str] = {
        "original_company_name": company_name,
        "original_website": website,
        "is_corrected": "false",
    }
    
    # 1. Fetch suggestions via OpenSearch
    suggestions = await fetch_nlp_typo_suggestions(clean_name)
    best_match = find_best_entity_match(clean_name, suggestions)
    
    corrected_name = clean_name
    if best_match and best_match.lower() != clean_name.lower():
        logger.info("NLP Typo Correction: %r -> %r (Candidates: %s)", clean_name, best_match, suggestions)
        corrected_name = best_match
        meta["is_corrected"] = "true"
        meta["corrected_from"] = clean_name
        meta["canonical_name"] = best_match
    
    # 2. Check if website domain matches company or if user provided a placeholder/typo domain
    try:
        parsed = urlparse(canonical_url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain = domain.lower().replace('www.', '')
        
        # If domain has obvious typo like 'microsft.com' when company is 'Microsoft'
        if corrected_name and domain:
            domain_name_part = domain.split('.')[0]
            clean_company_slug = re.sub(r'[^a-zA-Z0-9]', '', corrected_name.lower())
            if _levenshtein_distance(domain_name_part, clean_company_slug) in (1, 2) and len(domain_name_part) > 4:
                # User misspelled domain matching their misspelled company name
                tld = domain.split('.', 1)[1] if '.' in domain else 'com'
                canonical_url = f"https://www.{clean_company_slug}.{tld}"
                logger.info("NLP Domain Auto-Corrected: %r -> %r", domain, canonical_url)
                meta["auto_corrected_domain"] = canonical_url
    except Exception:
        pass
        
    return corrected_name, canonical_url, meta
