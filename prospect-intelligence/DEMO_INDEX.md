# Demo Index — All Testing Resources

Quick navigation to all demo and testing documentation.

## 📖 Quick Start (Start Here!)

**New to the tool?** Start with one of these:

1. **[DEMO_COMPANIES_QUICK_REF.md](./DEMO_COMPANIES_QUICK_REF.md)** ⭐ START HERE
   - One-page quick reference
   - 5 demo companies ready to test
   - Copy-paste instructions
   - 2 minutes to first result

2. **[INTEGRATION_GUIDE_RAG_ONLY.md](./INTEGRATION_GUIDE_RAG_ONLY.md)** ✅ FOR SETUP
   - Step-by-step server setup
   - Knowledge base ingestion guide
   - Pre-flight checklist
   - Troubleshooting help

---

## 🎯 Choose Your Testing Mode

### A. Real Company Testing (Recommended First)

**Best for**: Seeing the tool in action with real data

**Start with**: [DEMO_COMPANIES.md](./DEMO_COMPANIES.md)
- 5 real UK companies
- Mix of outcomes (High, Medium, Low scores)
- Tests source verification
- Shows realistic results

**Quick start**:
```
1. Open http://localhost:8000
2. Click "New Prospect"
3. Copy company from DEMO_COMPANIES.md
4. Paste name + website
5. Click "Start Research"
```

**Companies included**:
- Eden Facades Ltd (Strong-fit)
- Harley Facades Ltd (Strong-fit)
- Concept Facades Ltd (Mid-fit)
- Spotify (Poor-fit control)
- Harts Roofing (Minimal-web)

---

### B. Backend-Only Testing (Advanced)

**Best for**: Verifying anti-fabrication, deterministic scoring, RAG retrieval

**Start with**: [DEMO_TASKS_RAG_ONLY.md](./DEMO_TASKS_RAG_ONLY.md)
- 5 RAG-only demo tasks
- NO internet search (knowledge base only)
- Tests honesty and determinism
- For developers/QA

**Key differences**:
- No real company websites used
- All data from internal knowledge base
- Verify anti-fabrication works
- Check scoring determinism

**Companies included**:
- Coextend Internal Test (ICP alignment)
- Unknown Company XYZ 2024 (Anti-fabrication)
- Generic Construction Ltd (Deterministic scoring)
- Citation Test Company (Citation tracking)
- Message Template Test (Template generation)

---

## 📁 File Reference

### Demo Companies

| File | Purpose | Audience | Time |
|------|---------|----------|------|
| [DEMO_COMPANIES.md](./DEMO_COMPANIES.md) | Real companies with guide | Product/Sales team | 2-3 min |
| [DEMO_COMPANIES.csv](./DEMO_COMPANIES.csv) | CSV format for batch import | Developers | 1 min |
| [DEMO_COMPANIES_QUICK_REF.md](./DEMO_COMPANIES_QUICK_REF.md) | One-page quick reference | Everyone | 1 min |
| [DEMO_COMPANIES_RAG_ONLY.md](./DEMO_COMPANIES_RAG_ONLY.md) | RAG-only test scenarios | QA/Developers | 3-5 min |

### Demo Tasks & Integration

| File | Purpose | Audience | Time |
|------|---------|----------|------|
| [DEMO_TASKS_RAG_ONLY.md](./DEMO_TASKS_RAG_ONLY.md) | Detailed RAG-only tasks | Developers/QA | 5-10 min |
| [INTEGRATION_GUIDE_RAG_ONLY.md](./INTEGRATION_GUIDE_RAG_ONLY.md) | Server setup & verification | DevOps/Developers | 10-15 min |
| [INTEGRATION_PATCH.txt](./INTEGRATION_PATCH.txt) | Source verification code | Developers | 5 min |

### System Documentation

| File | Purpose | Audience |
|------|---------|----------|
| [SOURCE_VERIFICATION_FINAL_REPORT.md](./SOURCE_VERIFICATION_FINAL_REPORT.md) | Verification system details | Developers/Architects |
| [README.md](./README.md) | Full project documentation | Everyone |
| [DOCKER.md](./DOCKER.md) | Docker deployment guide | DevOps |

---

## 🚀 Testing Workflow

### For Product Demo (15 minutes)

1. Open http://localhost:8000
2. Use [DEMO_COMPANIES_QUICK_REF.md](./DEMO_COMPANIES_QUICK_REF.md)
3. Test Eden Facades (strong-fit)
4. Test Spotify (poor-fit)
5. Show scoring diversity
6. Demo CRM export
7. Show outreach templates

**Result**: Stakeholders see real capability

---

### For QA/Developer Testing (30-45 minutes)

1. Read [INTEGRATION_GUIDE_RAG_ONLY.md](./INTEGRATION_GUIDE_RAG_ONLY.md)
2. Start server and ingest knowledge base
3. Run all 5 RAG-only demo tasks ([DEMO_TASKS_RAG_ONLY.md](./DEMO_TASKS_RAG_ONLY.md))
4. Verify checklist items pass
5. Test real companies (compare to RAG-only)
6. Document findings

**Result**: Full validation of system behavior

---

### For Integration/DevOps (1-2 hours)

1. Read [DOCKER.md](./DOCKER.md)
2. Follow [INTEGRATION_GUIDE_RAG_ONLY.md](./INTEGRATION_GUIDE_RAG_ONLY.md)
3. Review [SOURCE_VERIFICATION_FINAL_REPORT.md](./SOURCE_VERIFICATION_FINAL_REPORT.md)
4. Check [INTEGRATION_PATCH.txt](./INTEGRATION_PATCH.txt)
5. Deploy with Docker Compose
6. Run verification tests
7. Set up monitoring

**Result**: Production-ready system

---

## 📊 Demo Company Matrix

**Choose based on what you want to test:**

| Want to See... | Use Company | Location |
|---|---|---|
| Full results (High score) | Eden Facades | DEMO_COMPANIES.md - Row 1 |
| Another high-scoring result | Harley Facades | DEMO_COMPANIES.md - Row 2 |
| Realistic medium score | Concept Facades | DEMO_COMPANIES.md - Row 3 |
| Correct rejection (poor-fit) | Spotify | DEMO_COMPANIES.md - Row 4 |
| Anti-fabrication in action | Harts Roofing | DEMO_COMPANIES.md - Row 5 |
| ICP matching from RAG | Coextend Internal Test | DEMO_COMPANIES_RAG_ONLY.md |
| Anti-fabrication verify | Unknown Company XYZ 2024 | DEMO_COMPANIES_RAG_ONLY.md |
| Deterministic scoring | Generic Construction Ltd | DEMO_COMPANIES_RAG_ONLY.md |
| Citation tracking | Citation Test Company | DEMO_COMPANIES_RAG_ONLY.md |
| Template generation | Message Template Test | DEMO_COMPANIES_RAG_ONLY.md |

---

## ✅ Verification Checklists

### After Each Demo Task

- [ ] Status updated (yellow → green)
- [ ] Brief generated
- [ ] Lead score calculated
- [ ] Sources listed
- [ ] Outreach templates shown
- [ ] No errors in logs

### After All Real Company Tests

- [ ] Eden scored High (70+)
- [ ] Spotify scored Low (20 or less)
- [ ] Concept scored Medium/Low (40-60)
- [ ] All sources are real
- [ ] Verification working

### After All RAG-Only Tests

- [ ] No internet sources used
- [ ] All citations from knowledge base
- [ ] Anti-fabrication working
- [ ] Scores deterministic
- [ ] sources_rejected populated

---

## 🎓 Learning Path

**Beginner** (Just want to see it work):
1. Read DEMO_COMPANIES_QUICK_REF.md (1 min)
2. Test Eden Facades (2 min)
3. Test Spotify (2 min)
4. Done! You've seen the tool in action

**Intermediate** (Want to understand scoring):
1. Read DEMO_COMPANIES.md (3 min)
2. Test all 5 real companies (15 min)
3. Review lead score breakdown
4. Understand source verification

**Advanced** (Want to verify system integrity):
1. Read INTEGRATION_GUIDE_RAG_ONLY.md (10 min)
2. Set up server & knowledge base (5 min)
3. Run all 5 RAG-only tasks (20 min)
4. Verify checklist (10 min)
5. Compare with real company testing (15 min)

---

## 🔗 Key Resources

**Setup & Running**:
- [START_SERVER.bat](./START_SERVER.bat) — Start the backend
- [DOCKER.md](./DOCKER.md) — Docker deployment
- [README.md](./README.md) — Full documentation

**Testing**:
- [DEMO_COMPANIES.md](./DEMO_COMPANIES.md) — Real companies
- [DEMO_TASKS_RAG_ONLY.md](./DEMO_TASKS_RAG_ONLY.md) — RAG-only tasks
- [DEMO_COMPANIES_RAG_ONLY.md](./DEMO_COMPANIES_RAG_ONLY.md) — RAG test cases

**Technical**:
- [SOURCE_VERIFICATION_FINAL_REPORT.md](./SOURCE_VERIFICATION_FINAL_REPORT.md) — Verification logic
- [INTEGRATION_PATCH.txt](./INTEGRATION_PATCH.txt) — Code integration
- [engine/source_verification.py](./engine/source_verification.py) — Verification engine

---

## ❓ FAQ

**Q: Where do I start?**
A: If new to the tool → DEMO_COMPANIES_QUICK_REF.md
   If setting up → INTEGRATION_GUIDE_RAG_ONLY.md

**Q: What's the difference between real and RAG-only testing?**
A: Real testing uses internet search + knowledge base (realistic)
   RAG-only uses only knowledge base (verification mode)

**Q: How long does a demo take?**
A: Quick demo (1 company): 2-3 minutes
   Full demo (5 companies): 15 minutes
   Full verification (real + RAG): 45 minutes

**Q: Can I use my own companies?**
A: Yes! Use the web form at http://localhost:8000
   Or API at POST /api/v1/prospects

**Q: What if I see web sources with RAG-only tasks?**
A: That means web search is still enabled
   Check config.py and restart server

---

## 📞 Support

**Issue with demo?**
- Check INTEGRATION_GUIDE_RAG_ONLY.md troubleshooting section
- Review logs at `data/logs/`
- Check database at `data/prospects.db`

**Issue with real companies?**
- Verify internet connection
- Check API rate limits
- Review source verification results

**Issue with RAG?**
- Ensure knowledge base ingested (POST /api/v1/knowledge/ingest)
- Check ChromaDB directory created
- Review ingestion logs

---

**Last Updated**: 2024
**Version**: 1.0
**Status**: ✅ Ready for Testing

