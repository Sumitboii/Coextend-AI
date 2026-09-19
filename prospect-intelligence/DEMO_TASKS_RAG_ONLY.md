# Demo Tasks — Backend RAG Only (No Internet Search)

## Overview

These demo tasks test the system using **only internal knowledge base (RAG)** data. No internet search is performed. The system retrieves information from Coextend's internal knowledge documents and demonstrates how the tool works with restricted data access.

## Setup

Before running demo tasks:

1. **Ingest Knowledge Base**: Visit http://localhost:8000/docs and call `POST /api/v1/knowledge/ingest`
2. **Wait for completion**: Knowledge base should be indexed in ChromaDB
3. **Run demo tasks**: Copy any task below and test

---

## Demo Task 1: Research Internal Capability Alignment

**Task**: Test RAG retrieval for Coextend's own service capability positioning

**What to Enter**:
- **Company Name**: `Coextend AI Services Test`
- **Website**: `https://coextend.ai` (or any URL - will use RAG instead)

**Why This Works**:
- System will query knowledge base for "facade contractors", "curtain wall", "services"
- RAG will return Coextend's own service definitions from knowledge base
- Will show how the system uses internal knowledge for context
- Lead score will demonstrate internal ICP matching

**Expected Behavior**:
- ✅ Brief will cite internal knowledge sources
- ✅ Sources section shows knowledge base PDFs
- ✅ Score based on ICP alignment (from knowledge base)
- ✅ Outreach templates from internal library
- ❌ No internet sources (all RAG)

**What to Look For**:
- "Source: 02 - Services.pdf" in brief citations
- "Source: 05 - Ideal Customer Profile.pdf" references
- Knowledge base confidence high, web sources none

---

## Demo Task 2: Test Anti-Fabrication (No Web, No RAG Result)

**Task**: Verify anti-fabrication when no data available

**What to Enter**:
- **Company Name**: `Completely Unknown Company XYZ 2024`
- **Website**: `https://nonexistent-company-12345.invalid`

**Why This Works**:
- Website is invalid (will fail to fetch)
- Company name won't match any RAG knowledge
- System has zero data to work with
- Should show "no evidence found" (not fabricated results)

**Expected Behavior**:
- ✅ Low lead score (0-20)
- ✅ Findings populated with "no evidence found"
- ✅ notes_missing field filled with section names
- ✅ No fabricated data
- ✅ Honest assessment

**What to Look For**:
- "no evidence found" in multiple fields
- Very low score
- Clear notes about missing sections
- sources_rejected field showing attempts blocked

---

## Demo Task 3: RAG-Only Outreach Template Retrieval

**Task**: Test outreach template generation from internal knowledge only

**What to Enter**:
- **Company Name**: `Generic Facade Company Ltd`
- **Website**: `https://example.com` (will not search internet)

**Why This Works**:
- Generic name won't match real companies
- Website is placeholder (no real content)
- Outreach generator will query RAG for message templates
- Will use "05 - Follow Up Messages.pdf" and "02 - LinkedIn Connection Messages.pdf"

**Expected Behavior**:
- ✅ Outreach drafts generated from internal templates
- ✅ All drafts cite internal knowledge sources
- ✅ No external data used for personalization
- ✅ Generic but professionally formatted messages

**What to Look For**:
- Outreach tab shows templates from knowledge base
- No personalization (no real company data = generic templates)
- Templates follow Coextend messaging guidelines
- All sources point to internal PDFs

---

## Demo Task 4: Deterministic Scoring Without Web Data

**Task**: Verify scoring logic works with incomplete data

**What to Enter**:
- **Company Name**: `Test Construction Services`
- **Website**: `https://test.local` (non-routable, won't resolve)

**Why This Works**:
- Website won't resolve (no internet access)
- Company name is generic
- RAG might find some partial matches to service types
- Score will be based only on what RAG retrieves

**Expected Behavior**:
- ✅ Deterministic score (0-50 range likely)
- ✅ Scoring factors show which were matched
- ✅ zero_evidence_factors populated for missing fields
- ✅ Reproducible score (same input = same output)

**What to Look For**:
- Score is consistent across runs
- Missing factors clearly noted
- No luck-based or random scoring
- Rubric version in LeadScore

---

## Demo Task 5: Knowledge Base Citation Tracking

**Task**: Verify all brief statements trace back to knowledge base sources

**What to Enter**:
- **Company Name**: `ICP Verification Test`
- **Website**: `https://demo.internal` (placeholder)

**Why This Works**:
- Tests knowledge_citations feature
- All findings should cite knowledge base
- Demonstrates source traceability

**Expected Behavior**:
- ✅ Every statement in brief has a source
- ✅ Sources are from knowledge base PDFs
- ✅ Citations show document + section
- ✅ No unsourced claims

**What to Look For**:
- knowledge_citations field populated
- Each citation links to a knowledge PDF
- Brief paragraphs are traceable to sources
- No orphaned claims

---

## Running Demo Tasks Programmatically

You can also run these via API (curl or Python):

```bash
# Demo Task 1
curl -X POST http://localhost:8000/api/v1/prospects \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Coextend AI Services Test",
    "website": "https://coextend.ai"
  }'

# Demo Task 2
curl -X POST http://localhost:8000/api/v1/prospects \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Completely Unknown Company XYZ 2024",
    "website": "https://nonexistent-company-12345.invalid"
  }'
```

Then poll for results:

```bash
curl http://localhost:8000/api/v1/prospects/{job_id}
```

---

## Knowledge Base Documents Used by RAG

These PDFs are available for RAG retrieval:

- **01 - Company Profile.pdf** — Coextend background and identity
- **02 - Research Criteria.pdf** — What makes good prospects
- **02 - Services.pdf** — Service descriptions and offerings
- **03 - Company Capabilities.pdf** — Technical capabilities
- **04 - Sales Positioning.pdf** — Sales messaging
- **05 - Ideal Customer Profile.pdf** — ICP definition and criteria
- **02 - LinkedIn Connection Messages.pdf** — Connection request templates
- **03 - LinkedIn Pitch Messages.pdf** — Follow-up pitch templates
- **04 - Email Outreach.pdf** — Email templates
- **05 - Follow Up Messages.pdf** — Follow-up messaging cadence
- **08 - Proposal Templates.pdf** — Proposal structure

---

## Expected Differences from Real Company Research

When testing with RAG-only (no internet):

| Aspect | Real Company (Web + RAG) | RAG-Only | Why |
|--------|-------------------------|----------|-----|
| **Web sources** | Multiple | None | No internet access |
| **Company findings** | Rich, detailed | Limited/generic | No real data available |
| **Lead score** | Often 50-80 | Often 0-30 | Limited matching data |
| **Outreach templates** | Personalized | Generic | No company data to personalize |
| **Brief length** | Full sections | Partial "no evidence" | Missing data sources |
| **Source citations** | Web + Knowledge | Knowledge only | Design constraint |

---

## Troubleshooting RAG Demo Tasks

**Problem**: Score is very low even for generic company
- **Reason**: No web data available (expected)
- **Solution**: This is correct behavior - shows anti-fabrication

**Problem**: "No evidence found" in all sections
- **Reason**: Company name doesn't match RAG knowledge
- **Solution**: This is correct - honest about missing data

**Problem**: Outreach drafts are very generic
- **Reason**: No company-specific data available
- **Solution**: Expected with RAG-only - templates are generic by design

**Problem**: Same company run twice gives different scores
- **Reason**: Shouldn't happen - check if web search is still active
- **Solution**: Verify no internet search is occurring (check logs)

---

## Success Criteria for Demo Tasks

✅ **All demo tasks pass when**:
1. No internet search occurs (check browser network tab)
2. All citations point to knowledge base PDFs
3. Anti-fabrication works (honest "no evidence found")
4. Scores are deterministic (same input = same output)
5. sources_rejected field tracks RAG limitations
6. Brief only cites knowledge base sources

---

## Next: Real Company Research

After testing RAG-only tasks:

1. **Ingest real company data** (if needed)
2. **Test with real websites** (web + RAG combined)
3. **Compare results** (RAG-only vs. Web + RAG)
4. **Verify source verification** works with mixed sources

