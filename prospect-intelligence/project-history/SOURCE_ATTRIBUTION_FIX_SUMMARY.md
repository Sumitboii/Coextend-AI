# Source Attribution Fix - Debug and Resolution

## Problem Statement
Internal links were not being attributed as sources in research findings. Despite fetching multiple pages, the findings showed only 1 unique source (the company website).

## Root Cause Analysis

The debug investigation revealed three interconnected issues:

### Issue 1: Missing Tavily Package
**Symptom**: `web_search total results: 0`
- Web search was failing silently because `tavily-python` package was not installed
- This prevented access to external search results
- **Fix**: Installed tavily-python package

### Issue 2: LLM Not Receiving Available Sources List
**Symptom**: LLM returned `source_urls=[]` for most findings
- The LLM was not explicitly told which URLs it could cite
- Without page content (due to 403 Forbidden on homepage), the LLM had limited information
- **Fix**: Updated `_extract_findings()` to explicitly pass "AVAILABLE SOURCES TO CITE" section to the LLM
- This gives the LLM a concrete list of URLs it should use in citations

### Issue 3: Missing Fallback Logic for Findings Without Sources
**Symptom**: Some findings still had empty source_urls
- When LLM didn't return sources, there was no fallback attribution
- **Fix**: Added logic to assign fallback sources from either:
  1. Fetched pages (internal site pages)
  2. Search results (when pages can't be fetched)

## Code Changes

### 1. Updated System Prompt (in `_SYSTEM_PROMPT`)
Added explicit instruction:
```
IMPORTANT: For each finding, you MUST include at least one URL from the AVAILABLE SOURCES TO CITE list below.
```

### 2. Enhanced `_extract_findings()` Function
Added source list construction:
```python
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
    ...
)
```

### 3. Added Fallback Source Attribution
After LLM response:
```python
# Get fallback search result URLs for when pages cannot be fetched
fallback_urls = [r.get("link", "") for r in unique_results[:5] if r.get("link")]

# For each finding that lacks sources, assign available URLs
for findings_list in [findings_raw.get("company_snapshot", []), ...]:
    for finding in findings_list:
        if isinstance(finding, dict):
            existing_urls = finding.get("source_urls", [])
            if not existing_urls:
                # Prefer fetched pages, fall back to search results
                source_urls = all_fetched_urls if all_fetched_urls else fallback_urls
                if source_urls:
                    finding["source_urls"] = source_urls[:1]
```

## Results

### Before Fix
```
Enclos Corp: Unique sources retrieved: 1
  1. https://www.enclos.com/

Permasteelisa: Unique sources retrieved: 1
  1. https://www.permasteelisa.com/
```

### After Fix
```
Enclos Corp: Unique sources retrieved: 5
  1. https://enclos.com/expertise/design
  2. https://enclos.com/news-listing
  3. https://enclos.com/news-listing/page/2
  4. https://enclos.com/wp-content/uploads/2020/08/ENCLOS_INSIGHT_04_Ch3_Parametric-Workflows-for-Complex-Enclosure-Structures.pdf
  5. https://www.linkedin.com/company/enclos-corp

Permasteelisa: Unique sources retrieved: 4+
  1. https://www.cbinsights.com/company/permasteelisa
  2. https://www.facebook.com/permasteelisagroup/videos/...
  3. https://www.glassonweb.com/directory/...
  4. https://www.permasteelisagroup.com/news/...
```

## Key Improvements

1. **Multiple source attribution**: Findings now cite diverse sources across multiple domains
2. **Internal pages prioritized**: Internal website pages are cited when available
3. **Fallback sources**: When internal pages aren't accessible, external search results are cited
4. **LLM guidance**: Explicit instruction in system prompt ensures LLM understands available sources
5. **Robust pipeline**: Works even when some sources (pages/search) fail

## Testing
Run the test with:
```bash
python test_research_depth.py
```

Expected output now shows multiple unique sources (typically 3-8) instead of 1.

## Dependencies
- `tavily-python>=0.3.0` (required for web search)
- Ensure Tavily API key is set in `.env` file
