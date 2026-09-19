# Research Depth Fix - Implementation Notes

## Change Summary

### File Modified
`engine/researcher.py`

### Changes Made

#### 1. New Helper Function: `_extract_internal_links()`
**Location**: Lines 281-314
**Responsibility**: Extract priority-matched internal links from company website homepage

**Algorithm**:
1. Parse domain from provided URL (netloc without www)
2. Extract all `href` attributes from page HTML using regex
3. Convert relative URLs to absolute using `urljoin`
4. Filter for internal links (same domain as input)
5. Further filter by priority keywords (project, case, about, team, services, news, etc.)
6. Deduplicate and return top 8 URLs

**Error Handling**: Wrapped in try-except; logs warning and returns empty list if extraction fails

#### 2. Enhanced `run_research()` Function
**Location**: Lines 317-475
**Key Changes**:

**a) Expanded Search Queries** (Lines 345-358)
- Increased from 5 to 10 search queries
- Added domain-specific `site:` searches for internal pages
- Added targeted queries for each key scoring criterion
- Examples:
  - `"{company} facade cladding curtain wall contractor"` - trade fit
  - `"site:{domain} projects case study"` - projects from company domain
  - `"{company} jobs hiring estimating BIM drafting"` - hiring signals
  - `"{company} tenders framework agreements"` - tender volume

**b) New Homepage-First Strategy** (Lines 365-372)
- Fetch company website homepage first (before other URLs)
- Store homepage content for internal link extraction
- Graceful error handling if homepage fetch fails

**c) Internal Link Extraction** (Lines 377-381)
- Call `_extract_internal_links()` on homepage content
- Extract up to 5 highest-priority internal subpages
- Add these to the pages-to-fetch list before search results

**d) Coordinated Page Fetching** (Lines 383-393)
- Fetch homepage first (done in step b)
- Build pages_to_fetch list: [homepage] + [internal links] + [search results]
- Fetch remaining pages (excluding already-fetched homepage)
- Track total pages fetched with debug logging

**e) Logging Enhancements**
- Added debug logs for:
  - Homepage fetch completion
  - Number of internal links extracted
  - Total pages fetched
  - Research phase completion

### Architectural Improvements

#### Before
```
Web Search
    ↓ (5 queries, 40 results max, dedup to ~10 unique)
    ↓
Page Fetching
    ↓ (1 homepage + 5 search results = 6 pages)
    ↓
LLM Extraction
    ↓
Scoring
```

#### After
```
Web Search
    ↓ (10 queries, 80 results max, dedup to ~20+ unique)
    ↓
Homepage Fetch
    ↓
    ├─→ Link Extraction (13 keywords)
    ↓
Internal Page Fetching (5 pages)
    ↓
External Page Fetching (5 search results)
    ↓
LLM Extraction (from 11-15 pages)
    ↓
Scoring
```

### Expected Results

#### Metrics Improvement

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Search Queries | 5 | 10 | 2x |
| Unique Result URLs | ~10 | ~20+ | 2x+ |
| Pages Fetched | 6 | 11-15 | 2x |
| Internal Subpages | 0 | 5 | ∞ |
| projects_signals Entries | Often 0-1 | 3+ | 3-10x |
| Evidence Coverage | Partial | Comprehensive | 2-3x |

#### Evidence Gathering

**Projects/Services Evidence**: Now found from:
- `/projects`, `/portfolio`, `/case-studies` pages
- Project press releases and announcements
- Portfolio/expertise sections

**Team/Decision Makers**: Now found from:
- `/about`, `/team`, `/leadership` pages
- Management team directories
- Press releases mentioning executives

**Company Size**: Now found from:
- `/careers` or `/jobs` pages (team size hints)
- `/investors` or financial reports
- Company profile searches

**Tenders/Outsourcing**: Now found from:
- Dedicated `site:` search for contracts
- News/press releases about awards
- Business type and specialization pages

### Code Quality Aspects

✅ **Backward Compatibility**:
- No breaking changes to function signatures
- No database schema changes
- No API contract changes
- Existing code paths unaffected

✅ **Error Resilience**:
- Each page fetch wrapped in try-except
- Missing homepage doesn't break workflow
- Failed link extraction returns empty list
- All fetch errors logged and continue

✅ **Performance**:
- URL deduplication prevents redundant fetches
- Early homepage fetch enables link extraction before search results
- Parallel-ready (each fetch is independent)
- Timeout-safe (uses existing `fetch_page` which has timeouts)

✅ **Maintainability**:
- Well-documented with inline comments
- Clear variable names (e.g., `pages_to_fetch_remaining`)
- Isolated logic in helper function
- Consistent with existing code style

✅ **Debuggability**:
- Debug logging at key checkpoints
- Count logging for research metrics
- Warning logs for all error conditions
- Structured logging with job_id and company

### Testing Strategy

**Unit Test Coverage**:
1. `_extract_internal_links()` with various HTML structures
2. `run_research()` with real company URLs
3. Edge cases: missing homepage, empty links, timeout scenarios

**Integration Test Coverage**:
1. End-to-end with Enclos Corp (known good company)
2. End-to-end with Permasteelisa (international case)
3. Verify scoring increases with richer evidence

**Validation Checkpoints**:
1. No syntax errors ✅
2. Type hints present ✅
3. Graceful error handling ✅
4. Logging present ✅
5. Backward compatible ✅
6. Search queries expanded ✅
7. Internal links extracted ✅
8. Pages fetched increased ✅

### Known Limitations

1. **JavaScript-Heavy Sites**: Internal link extraction works on static HTML only
   - Workaround: Tavily search results may catch dynamically-generated pages
   - Future: Could integrate Selenium for JS rendering

2. **Rate Limiting**: More searches and fetches increase API call volume
   - Mitigated by: Existing backoff/retry logic in fetch_page
   - Future: Could implement caching for repeated companies

3. **Page Size Limit**: Max 30KB per page (existing constraint)
   - Still captures most important content (homepage, projects, team pages typically <30KB)
   - Truncation handled gracefully

4. **Search Result Variability**: Tavily results may vary by query/time
   - Acceptable: Evidence aggregation handles missing data
   - Design: LLM extraction marked fields as "Unverified" if not found

### Rollback Instructions

If the implementation causes issues:

1. Revert researcher.py to previous version:
   ```bash
   git checkout HEAD -- engine/researcher.py
   ```

2. No migration needed (no database changes)

3. Existing jobs unaffected (data format unchanged)

4. Immediately re-deployable (no dependency changes)

### Performance Impact

**API Calls**:
- +5 additional web searches (+40 result snippets to process)
- +5-8 additional page fetches

**LLM Tokens**:
- More page content (~3-4x more text) = more tokens
- Estimated: 5,000 → 15,000 tokens per company research
- Cost: Minimal (Gemini Flash-Lite very low cost)

**Execution Time**:
- Parallel nature: fetches run sequentially but fast
- Estimated increase: +5-10 seconds per company (mostly network latency)

## Code Review Checklist

- [x] Function signatures unchanged (backward compatible)
- [x] No new dependencies added
- [x] Error handling comprehensive
- [x] Logging at appropriate levels
- [x] Type hints present and correct
- [x] Comments explain non-obvious logic
- [x] Variable names descriptive
- [x] DRY principle followed (link dedup logic)
- [x] No hardcoded values or credentials
- [x] Consistent with codebase style

## Future Enhancements

1. **Adaptive Search**: Adjust queries based on domain TLD, company sector
2. **Link Prioritization**: Score internal links by relevance
3. **Pagination**: Follow "More Projects" links automatically
4. **Document Type Priority**: Prioritize PDFs (whitepapers, case studies)
5. **Freshness Tracking**: Note "recent" vs "archived" content
6. **Recursive Crawling**: Limited 2-level crawl for project detail pages
7. **Content Deduplication**: Avoid indexing similar pages (e.g., project listings)

## References

- Original Issue: "Research engine retrieves only 1 source per company"
- Root Cause: Limited search queries (5) + no internal page crawling
- Solution Design: Expand queries (10+) + internal link extraction
- Implementation File: `engine/researcher.py`
- Test File: `test_research_depth.py` (created)
- Documentation: `RESEARCH_DEPTH_FIX.md` (created)
