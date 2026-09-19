# Demo Companies — RAG-Only Testing (Backend Knowledge Base Only)

**Important**: These demo tasks use **ONLY the internal knowledge base (RAG)** — no internet search. The system retrieves data from Coextend's internal documents in `data/knowledge_base/` and demonstrates knowledge-grounded research.

## Quick Start

1. **Ingest Knowledge Base**: POST to `/api/v1/knowledge/ingest`
2. **Copy any company below** into the form
3. **Paste website** (can be placeholder, won't search internet)
4. **Click "Start Research"**
5. **Observe**: All sources come from internal PDFs

---

## 5 RAG-Only Demo Tasks

| Task # | Test Name | Company | Website | Purpose | Expected Score |
|--------|-----------|---------|---------|---------|-----------------|
| **1** | ICP Alignment | `Coextend Internal Test` | `https://internal.local` | Test RAG retrieval of internal ICP | Medium (30-50) |
| **2** | Anti-Fabrication | `Unknown Company XYZ 2024` | `https://fake.invalid` | Verify "no evidence found" | Low (0-20) |
| **3** | Generic Research | `Generic Construction Ltd` | `https://test.local` | Test deterministic scoring | Low (10-30) |
| **4** | Knowledge Citation | `Citation Test Company` | `https://demo.internal` | Verify knowledge_citations tracking | Low (10-25) |
| **5** | Outreach Only | `Message Template Test` | `https://example.local` | Test template generation from RAG | Low (5-20) |

---

## How to Test

### Task 1: ICP Alignment (RAG Knowledge Retrieval)

**Enter**:
- Company Name: `Coextend Internal Test`
- Website: `https://internal.local`

**What Happens**:
- System queries RAG for ICP information
- Retrieves from `05 - Ideal Customer Profile.pdf`
- Uses `02 - Research Criteria.pdf` for matching
- No internet search occurs

**What You'll See**:
- ✅ Brief cites internal PDFs
- ✅ Score based on internal ICP
- ✅ All sources from knowledge base
- ❌ No web sources

---

### Task 2: Anti-Fabrication (No Data Available)

**Enter**:
- Company Name: `Unknown Company XYZ 2024`
- Website: `https://fake.invalid`

**What Happens**:
- Website fails (invalid domain, won't search anyway)
- Company name matches no RAG knowledge
- System has zero data
- Should refuse to fabricate

**What You'll See**:
- ✅ Low score (0-20)
- ✅ "no evidence found" throughout
- ✅ notes_missing populated
- ✅ Honest "insufficient data" messages

---

### Task 3: Generic Research (Deterministic Scoring)

**Enter**:
- Company Name: `Generic Construction Ltd`
- Website: `https://test.local`

**What Happens**:
- No real company data available
- RAG might find partial service matches
- Scoring is purely deterministic

**What You'll See**:
- ✅ Consistent score across runs
- ✅ zero_evidence_factors clear
- ✅ Scoring factors documented
- ✅ Same input = same score

---

### Task 4: Knowledge Citation Tracking

**Enter**:
- Company Name: `Citation Test Company`
- Website: `https://demo.internal`

**What Happens**:
- Tests knowledge_citations field
- Every brief statement should cite source
- All sources are internal PDFs

**What You'll See**:
- ✅ knowledge_citations populated
- ✅ Each citation links to PDF + section
- ✅ No unsourced statements
- ✅ Full traceability

---

### Task 5: Outreach Template Generation

**Enter**:
- Company Name: `Message Template Test`
- Website: `https://example.local`

**What Happens**:
- System retrieves outreach templates from RAG
- Uses `02 - LinkedIn Connection Messages.pdf`
- Uses `04 - Email Outreach.pdf`
- Generates generic (non-personalized) templates

**What You'll See**:
- ✅ Email templates from internal library
- ✅ LinkedIn messages from knowledge base
- ✅ Generic (not personalized to company)
- ✅ All sources point to internal PDFs

---

## Knowledge Base Documents Available for RAG

All these PDFs are indexed and queryable:

| Document | Purpose | Used For |
|----------|---------|----------|
| 01 - Company Profile | Coextend background | Context |
| 02 - Research Criteria | Prospect evaluation | Scoring |
| 02 - Services | Service descriptions | Capability matching |
| 03 - Company Capabilities | Technical details | ICP matching |
| 04 - Sales Positioning | Sales messaging | Brief recommendations |
| 05 - Ideal Customer Profile | ICP definition | Lead scoring |
| 02 - LinkedIn Messages | Connection templates | Outreach generation |
| 04 - Email Outreach | Email templates | Outreach generation |
| 05 - Follow Up Messages | Follow-up cadence | Multi-touch sequences |

---

## Verification Checklist

After running demo tasks, verify:

- [ ] No internet search occurred (check network tab)
- [ ] All sources are from knowledge base PDFs
- [ ] sources_rejected field shows why sources excluded
- [ ] Anti-fabrication working ("no evidence found" not guesses)
- [ ] Scores deterministic (same input = same output)
- [ ] knowledge_citations fully populated
- [ ] Outreach templates from internal library

---

## Difference: Web-Only vs. RAG-Only

| Feature | Web Search | RAG-Only |
|---------|-----------|----------|
| Internet access | Yes | ❌ No |
| Company data | Real/actual | No data |
| Knowledge base | Supplementary | ✅ Primary |
| Score range | Usually 40-80 | Usually 0-30 |
| Findings | Detailed | Generic/"no evidence" |
| Citations | Web + PDFs | ✅ PDFs only |
| Outreach | Personalized | Generic templates |
| Speed | Slower (web requests) | ✅ Faster (local RAG) |

---

## Success Indicators

✅ **RAG-Only demo passes when**:
1. No internet requests made
2. All citations from knowledge base
3. Anti-fabrication active ("no evidence")
4. Deterministic scores
5. sources_rejected field populated
6. Zero external sources used

❌ **If you see**:
- Web sources cited (like "wikipedia.com")
- Hallucinated company facts
- Non-deterministic scores
- External URLs in sources

→ Then web search is still active (not RAG-only mode)

---

## Next Steps

1. ✅ Run all 5 RAG-only demo tasks
2. ✅ Verify all checks pass
3. ✅ Test with real companies (web + RAG)
4. ✅ Compare results between modes

