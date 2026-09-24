# Coextend AI — Prospect Intelligence MVP

An autonomous AI-powered pre-construction prospect research and intelligence system built for **Coextend Global LLP**. Given a prospective company name and website, the system executes real-time web research, deterministically scores commercial fit against a 100-point ICP rubric, grounds company positioning against internal technical standards (CWCT, BS EN 13830, ASTM) via ChromaDB RAG, and produces decision-ready executive briefs, CRM-ready exports (HubSpot), and tailored outreach drafts.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)
[![Live on Render](https://img.shields.io/badge/Live_App-Render-success?style=for-the-badge&logo=render)](https://coextend-ai.onrender.com)

---

## 🌐 Live Production Deployment
- **Live Web Application:** [https://coextend-ai.onrender.com](https://coextend-ai.onrender.com)
- **Interactive Swagger API Docs:** [https://coextend-ai.onrender.com/docs](https://coextend-ai.onrender.com/docs)
- **Health Check Endpoint:** [https://coextend-ai.onrender.com/api/v1/health](https://coextend-ai.onrender.com/api/v1/health)

---

## 👨‍💻 Project Information & Developer
- **Developer / AI Engineer:** **Sumit Singh** ([@Sumitboii](https://github.com/Sumitboii))
- **Email:** `ssingh46681@gmail.com`
- **Role:** AI Automation Engineer
- **Project Assessment:** Coextend AI Automation Engineer — Pilot Project Implementation
- **Status:** **Completed & Verified (233/233 Automated Tests Passing)**

---

## 🚀 Key Capabilities

1. **Deterministic 100-Point Lead Scoring:**
   - 10-factor weighted scoring implemented in pure Python (`scoring/engine.py`), completely eliminating non-deterministic LLM scoring drift.
   - 5-Tier ICP priority classification:
     - `80–100`: **A+ / Priority**
     - `65–79`: **A / Strong fit**
     - `50–64`: **B / Nurture**
     - `35–49`: **C / Low priority**
     - `0–34`: **D / Disqualify**

2. **Grounded Internal Knowledge (RAG Layer):**
   - Ingests 14 proprietary Coextend knowledge base documents into a ChromaDB vector index.
   - Generates cited executive briefs and Scope of Work proposals referencing exact standards (CWCT, Bluebeam, Revit).

3. **External Real-Time Web Research Engine:**
   - Asynchronous multi-stage external research via Tavily API with high-resilience fallback scraping.
   - Extracts key decision-makers (Managing Director, Commercial Director, Pre-Construction Director, Estimating Manager).

4. **Strict Anti-Fabrication & Evidence Classification (Req 8.1, 2.6):**
   - Pre-validation and source verification filter out wrong-company directory pages and demo portals.
   - Heuristic fallback strictly protects against false commercial sector assignment: educational, governmental, healthcare, legal, and non-profit entities are never mapped to construction or retail trades.
   - Every material claim is labeled as `[Verified]`, `[Probable]`, or `[Unverified]` with exact source URL citations.
   - Outputs `"no evidence found"` when data is absent instead of hallucinating.

5. **CRM-Ready Export & Outreach Drafts:**
   - Direct JSON and CSV export mapped to HubSpot Contact / Company / Deal schemas.
   - Duplicate prospect detection surfaces existing records without creating new files (Req 8.5).
   - Character-limited LinkedIn connection notes (<300 chars) and 3-step cold email cadences.

6. **Interactive Demo Showcase:**
   - Zero-backend standalone static showcase in `static-demo/index.html` (and `docs/index.html`).

---

## 📁 Repository Structure

```
├── prospect-intelligence/        # Core FastAPI Application & Engine
│   ├── api/                      # Routes, database models, CRM adapter, feedback service
│   ├── engine/                   # External research, pure Python scoring, brief & proposal generators
│   ├── knowledge/                # ChromaDB ingestion and grounded RAG retrieval
│   ├── scoring/                  # Deterministic 100-point rubric and test suites
│   ├── ui/                       # Frontend templates (Jinja2 + Tailwind) & Service Worker
│   ├── tests/                    # 233 comprehensive automated tests
│   ├── Dockerfile                # Multi-stage production container
│   ├── render.yaml               # 1-Click Render deployment configuration
│   └── requirements.txt          # Python dependencies
├── static-demo/                  # Standalone zero-backend interactive showcase
│   └── index.html
├── docs/                         # GitHub Pages deployment files
│   └── index.html
├── Project_PDFs_and_Presentations/ # Ingested Coextend Knowledge Base Documents
├── requirements.md               # Product Requirements Document (PRD)
├── render.yaml                   # Root Render blueprint deployment configuration
└── README.md                     # Project documentation
```

---

## 🛠️ Quick Start & Local Execution

### Prerequisites
- Python 3.11+
- Virtual environment (`venv`)

### Installation & Run

```bash
# 1. Navigate to the prospect-intelligence directory
cd prospect-intelligence

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Ingest knowledge base PDFs into ChromaDB
python ingest_kb.py

# 5. Run the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Open **http://localhost:8000** in your browser to access the dashboard.

---

## 🧪 Running Automated Tests

```bash
cd prospect-intelligence
pytest -v
```
All **233 tests** will execute across anti-fabrication, scoring determinism, CRM adapters, non-commercial entities, and end-to-end pipelines.

---

## ☁️ Deployment (Render / Docker)

This application includes ready-to-use Docker and Render configurations:
- **Render Web Service:** Uses `render.yaml` with automatic `$PORT` binding.
- **Static Demo:** Deploy `static-demo/index.html` directly to GitHub Pages or Render Static Sites.

---
Developed by **Sumit Singh** for **Coextend Global LLP**.
