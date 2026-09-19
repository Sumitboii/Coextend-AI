# Coextend Prospect Intelligence MVP - Complete Project Context

## TABLE OF CONTENTS
- Project Overview
- Architecture & Tech Stack  
- Current Status
- Database & Storage
- UI/UX Updates
- Key Features
- Requirements Summary
- Implementation Tasks
- Testing & Quality
- Cost & Roadmap
- Known Limitations

---

## PROJECT OVERVIEW

**Coextend Prospect Intelligence MVP** is an AI-assisted prospect research system.

### CORE PURPOSE
Given company name + website → System:
1. Researches prospect via public web (5 queries, 6 page fetches)
2. Grounds in Coextend PDFs (RAG, ChromaDB, 15 documents)
3. Scores deterministically (0-100, 10-factor rubric, PURE CODE - NO LLM)
4. Produces research brief (11 sections with citations)
5. Exports CRM record (JSON/CSV for HubSpot)
6. Drafts outreach (email + LinkedIn, draft-only, never sent)

### KEY GUARANTEES
✅ NEVER INVENTS FACTS - all claims have source URLs + evidence labels
✅ NO LIVE CRM WRITES - mock adapter, local files only
✅ NO LINKEDIN AUTOMATION - drafts only, founder reviews
✅ DETERMINISTIC SCORING - same data = same score (tested)

---

## ARCHITECTURE & TECH STACK

### COMPONENTS
Research Engine (web search + LLM extraction)
Scoring Engine (pure deterministic code, 10 factors)
Brief Generator (LLM + RAG retrieval)
CRM Adapter (MockHubSpot JSON/CSV)
Outreach Generator (LLM + message templates)
Knowledge Index (ChromaDB, 15 Coextend PDFs)

### TECH STACK
Language: Python 3.11+
Framework: FastAPI (async, auto-docs /docs)
Database: SQLite + SQLAlchemy async
Vector Store: ChromaDB (coextend_knowledge collection)
LLM: OpenAI GPT-4o (JSON schema mode, temp=0)
Embeddings: text-embedding-3-small
Web Search: Serper.dev (5 queries, 8 results each)
HTTP Client: httpx (async, 20s timeout)
Retry: tenacity @retry (3 attempts, 1.5s base, 30s max)
UI: Jinja2 (no JS framework)
Tests: pytest + pytest-asyncio (108 tests)

---

## CURRENT STATUS

✅ COMPLETED
- FastAPI scaffolding
- 12 Pydantic v2 models
- SQLite database + ORM
- RAG knowledge index
- Web research engine (search + fetch + retry)
- Deterministic scoring (10 factors)
- Brief generator (anti-fabrication checks)
- CRM export (JSON/CSV)
- Outreach drafts (email + LinkedIn)
- Web UI (form + polling)
- Logging + error handling
- 108 passing tests

🚀 RUNNING NOW
Server: http://localhost:8000
API Docs: http://localhost:8000/docs
Database: data/prospect_intelligence.db
Exports: data/exports/

🎨 LATEST UI UPDATES
✅ Header: Blue gradient (#0066cc) + white text
✅ History: 📋 button in header, shows past 20 searches
✅ Animations: 0.3s fade-out before redirect
✅ Theme: Blue, dark navy, white
✅ Feedback: Kept as tab in results

---

## DATABASE & STORAGE

### SQLITE DATABASE
Location: data/prospect_intelligence.db
Tables: jobs, findings, lead_scores, briefs, crm_exports, outreach_drafts

Views:
- vw_jobs_by_score_desc
- vw_jobs_by_band
- vw_failed_jobs

Open with DB Browser for SQLite (free)

---

## KEY FEATURES

### 1. PROSPECT SUBMISSION
POST /api/v1/prospects
Returns: job_id, status=pending, duplicate_warning
24-hour duplicate check (warning, not rejection)

### 2. RESEARCH PIPELINE
Status: pending → researching → scoring → drafting → complete (or failed)

Research Engine:
- 5-10 queries
- 6 page fetches
- Evidence labels: Verified (≥2 sources), Probable (1), Unverified (0)
- Retry: 3 attempts, exponential backoff

Scoring Engine:
- Pure code (NO LLM)
- 10 factors
- 0-100 score
- Band (5-tier ICP classification): A+ / Priority (80-100), A / Strong fit (65-79), B / Nurture (50-64), C / Low priority (35-49), D / Disqualify (0-34)
- Repeatability: same input = same output (guaranteed by tests)

Brief Generator:
- LLM + RAG retrieval
- 9 sections + lead score + sources
- Post-generation label validation
- 120s timeout
- LLM re-prompt once on malformed JSON

### 3. KNOWLEDGE INDEX
POST /api/v1/knowledge/ingest
- 15 Coextend PDFs
- Heading-aware chunking
- ChromaDB storage
- Atomic re-ingestion

### 4. CRM EXPORT
GET /api/v1/prospects/{id}/crm-export
JSON or CSV format
HubSpot-style fields
Duplicate detection
No live CRM writes

### 5. OUTREACH DRAFTS
POST /api/v1/prospects/{id}/outreach
Email (≤200 words) + LinkedIn (≤300 chars)
Draft-only (status locked to "draft")
No send/schedule capability

---

## TESTING & QUALITY

### 108 PASSING TESTS
test_models.py - validation
test_scoring.py - all 10 factors + repeatability
test_anti_fabrication.py - zero-evidence + labels
test_failure_injection.py - error handling
test_e2e_prospects.py - 5 archetypes
test_crm_adapter.py - exports + duplicates

Run: pytest prospect-intelligence/

---

## COST ESTIMATE

100/mo: ~$12
500/mo: ~$58
2000/mo: ~$231

---

## SETUP & QUICK START

Installation:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

Config:
copy .env.example .env
Edit with OPENAI_API_KEY and SEARCH_API_KEY

Run:
uvicorn main:app --reload
OR: START_SERVER.bat

API: http://localhost:8000/docs

Tests: pytest prospect-intelligence/

---

## ROADMAP

30 DAYS: Cloud deploy, API auth, 20-prospect validation
60 DAYS: Human review UI, CSV import, live HubSpot adapter
90 DAYS: Evaluation framework, approval queue, dashboard

---

## KEY FILES

Models: api/models.py
Scoring: scoring/engine.py, scoring/rubric.py
Research: engine/researcher.py
Brief: engine/brief_generator.py
Tests: tests/ (108 tests)
Database: data/prospect_intelligence.db

---

## STATUS

✅ MVP COMPLETE | 🚀 SERVER RUNNING | 📊 108 TESTS PASSING | 🎨 UI STYLED

Generated: Latest Session
