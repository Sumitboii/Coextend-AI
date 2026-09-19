# Integration Guide — RAG-Only Demo Tasks

## 1️⃣ Pre-Flight Checklist

Before running demo tasks, verify everything is ready:

- [ ] **Server Running**: http://localhost:8000/api/v1/health returns `{"status":"ok"}`
- [ ] **Knowledge Base Ingested**: Run `POST /api/v1/knowledge/ingest` (see Step 2)
- [ ] **Database Ready**: SQLite DB initialized
- [ ] **ChromaDB Running**: Vector database for RAG ready
- [ ] **Demo Files Present**: DEMO_COMPANIES_RAG_ONLY.md, DEMO_TASKS_RAG_ONLY.md exist

---

## 2️⃣ Start Server

Start the Prospect Intelligence backend:

### Option A: Using START_SERVER.bat (Windows)
```batch
cd prospect-intelligence
START_SERVER.bat
```

### Option B: Direct Python
```bash
cd prospect-intelligence
python main.py
```

**Expected Output**:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Verify**: http://localhost:8000/api/v1/health → `{"status":"ok"}`

---

## 3️⃣ Ingest Knowledge Base

The system needs to index PDFs into ChromaDB for RAG retrieval.

### Option A: Via UI (Recommended)
1. Open http://localhost:8000
2. Click "API Docs" (top right)
3. Find `POST /api/v1/knowledge/ingest`
4. Click "Try it out"
5. Click "Execute"
6. Wait for completion (1-2 minutes)

### Option B: Via curl
```bash
curl -X POST http://localhost:8000/api/v1/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Option C: Direct Python
```bash
python ingest_kb.py
```

**Expected Response**:
```json
{
  "status": "success",
  "documents_ingested": 17,
  "chunks_created": 150+,
  "vector_db": "ready"
}
```

**Verify**: ChromaDB should have ~150 document chunks indexed

---

## 4️⃣ Run RAG-Only Demo Tasks

### Demo Task 1: ICP Alignment

**Enter into form**:
- Company Name: `Coextend Internal Test`
- Website: `https://internal.local`

**Expected**:
- Score: 30-50 (partial ICP match from RAG)
- Sources: All from knowledge base PDFs
- Brief mentions: Service types, capabilities from internal docs
- Outreach: Generic templates from internal library

**Verify**:
- ✅ No internet requests (check browser Network tab)
- ✅ All citations from knowledge base
- ✅ sources list shows PDFs (not web URLs)
- ✅ sources_rejected populated

---

### Demo Task 2: Anti-Fabrication

**Enter into form**:
- Company Name: `Unknown Company XYZ 2024`
- Website: `https://fake.invalid`

**Expected**:
- Score: 0-20 (very low, no data)
- Brief: Shows "no evidence found" throughout
- sources_rejected: Explains why website failed
- notes_missing: Lists all missing sections

**Verify**:
- ✅ No fabricated company facts
- ✅ Honest "no evidence found" messaging
- ✅ Low score correctly reflects no data
- ✅ Anti-fabrication logic working

---

### Demo Task 3: Generic Research (Deterministic)

**Enter into form**:
- Company Name: `Generic Construction Ltd`
- Website: `https://test.local`

**Expected**:
- Score: 10-30 (generic, limited match)
- Same score on repeat runs
- Deterministic factors documented

**Run Twice**:
1. First run: Note the score and factors
2. Second run: Should get IDENTICAL score
3. Compare: Verify determinism (not random)

**Verify**:
- ✅ Score identical on repeat
- ✅ Factors reproducible
- ✅ No luck/randomness in scoring

---

### Demo Task 4: Knowledge Citation Tracking

**Enter into form**:
- Company Name: `Citation Test Company`
- Website: `https://demo.internal`

**Expected**:
- Every statement in brief has source
- knowledge_citations field fully populated
- Each citation shows: PDF name + section

**Check Brief**:
- Hover over citations (or view source)
- Each cite should show: "Source: 05 - Ideal Customer Profile.pdf"
- No orphaned statements without sources

**Verify**:
- ✅ knowledge_citations populated
- ✅ All briefs cite internal PDFs
- ✅ No unsourced claims

---

### Demo Task 5: Outreach Template Generation

**Enter into form**:
- Company Name: `Message Template Test`
- Website: `https://example.local`

**Click "Outreach" tab**:
- Email template should appear
- LinkedIn message should appear
- Messages are generic (not personalized)

**Verify**:
- ✅ Outreach tab shows templates
- ✅ Templates from internal library
- ✅ All cite internal PDFs as source
- ✅ Generic (no real company data)

---

## 5️⃣ Verification Checklist

After running all 5 demo tasks, verify:

### RAG-Only Data Sources
- [ ] No URLs from wikipedia, google, linkedin, etc. in sources
- [ ] All sources point to PDFs in `data/knowledge_base/`
- [ ] sources_rejected explains what was excluded

### Anti-Fabrication
- [ ] Unknown companies show "no evidence found" (not guesses)
- [ ] Low scores when data missing (not inflated)
- [ ] notes_missing populated for empty sections
- [ ] No hallucinated company facts

### Deterministic Scoring
- [ ] Run same company twice → same score
- [ ] Scoring factors reproducible
- [ ] rubric_version documented
- [ ] zero_evidence_factors clear

### Knowledge Citations
- [ ] Every brief statement has citation
- [ ] knowledge_citations field complete
- [ ] Citations link to internal PDFs
- [ ] No external sources in brief

### Outreach Templates
- [ ] All templates from internal library
- [ ] Email drafts are generic
- [ ] LinkedIn messages not personalized
- [ ] All sources are internal PDFs

---

## 6️⃣ Troubleshooting

### Issue: Server won't start
```
Error: Address already in use
```
**Solution**: Kill process on port 8000
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Issue: Knowledge base ingestion times out
```
Timeout after 30 seconds
```
**Solution**: Expected behavior (processing ~17 PDFs)
- Wait 2-3 minutes
- Check if ChromaDB directory created
- Restart server after ingestion completes

### Issue: Demo tasks show web sources
```
"source": "https://wikipedia.com"
```
**Solution**: Web search is still active (not RAG-only mode)
- Check `config.py` — ensure `SEARCH_ENABLED = False`
- Restart server
- Try demo task again

### Issue: Scores not deterministic
```
Run 1: Score 45
Run 2: Score 52
```
**Solution**: Check if RAG retrieval is non-deterministic
- Verify ChromaDB is properly indexed
- Check logs for retrieval variance
- Ensure similarity threshold is consistent

### Issue: Sources show external URLs
```
"source": "https://company-website.com"
```
**Solution**: Backend is still searching internet
- Set `SEARCH_ENABLED = False` in config
- Disable internet search in researcher.py
- Restart server
- Re-run demo task

---

## 7️⃣ What Each Demo Task Demonstrates

| Task | Demonstrates | Key Learning |
|------|--------------|--------------|
| **ICP Alignment** | RAG knowledge retrieval | System queries internal knowledge correctly |
| **Anti-Fabrication** | Honest "no evidence" | Tool won't guess with missing data |
| **Generic Research** | Deterministic scoring | Scores are reproducible, not random |
| **Knowledge Citation** | Citation tracking | All findings traceable to sources |
| **Outreach Templates** | Template generation | Messaging from internal library |

---

## 8️⃣ Moving Beyond Demo Tasks

After verifying RAG-only mode works:

### Test with Real Companies (Web + RAG)
```bash
# Configure for web search
# Set SEARCH_ENABLED = True in config.py
# Restart server

# Test real company
curl -X POST http://localhost:8000/api/v1/prospects \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Eden Facades Ltd",
    "website": "https://edenfacades.com"
  }'
```

### Compare Results
- RAG-Only: Limited, generic results
- Web + RAG: Rich, real company data
- Both: Accurate, sourced, traceable

---

## 9️⃣ Key Files Reference

| File | Purpose |
|------|---------|
| `DEMO_COMPANIES_RAG_ONLY.md` | 5 RAG-only demo companies |
| `DEMO_TASKS_RAG_ONLY.md` | Detailed task instructions |
| `DEMO_COMPANIES_QUICK_REF.md` | Quick reference for real companies |
| `INTEGRATION_PATCH.txt` | Source verification integration code |
| `SOURCE_VERIFICATION_FINAL_REPORT.md` | Verification system documentation |
| `engine/source_verification.py` | Source matching & verification logic |

---

## 🔟 Success Criteria

✅ **RAG-only demo tasks pass when:**

1. **No Internet Search**
   - Browser Network tab shows no external requests
   - All sources are local PDFs

2. **Anti-Fabrication**
   - Unknown companies show "no evidence"
   - No hallucinated facts

3. **Deterministic**
   - Same input → Same score
   - Reproducible factors

4. **Fully Cited**
   - Every statement has source
   - knowledge_citations populated

5. **Internal Only**
   - All sources from `data/knowledge_base/`
   - No external URLs

✅ **Then you're ready for:**
- Production deployment
- Real company testing (web + RAG)
- Team demonstrations
- Integration with CRM

