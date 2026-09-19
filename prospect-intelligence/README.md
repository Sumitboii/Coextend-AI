# Coextend Prospect Intelligence MVP

AI-assisted prospect research system for Coextend Global LLP.  
Given a company name and website, it researches the prospect, scores them
deterministically against Coextend's ICP rubric, and produces a
founder-ready brief, a CRM-ready export, and optional outreach drafts.

---

## Architecture Summary

```
Web UI (Jinja2) → FastAPI → async pipeline
  ├── Research Engine (web search + LLM extraction → ResearchFindings)
  ├── Scoring Engine  (deterministic code → LeadScore 0–100)
  ├── Brief Generator (LLM + RAG → ResearchBrief with citations)
  ├── CRM Adapter     (MockHubSpotAdapter → JSON/CSV to /data/exports/)
  └── Outreach Generator (LLM + message-library RAG → drafts only)

Internal Knowledge (ChromaDB):
  Coextend PDFs ingested once → top-k retrieval with citations
  Kept strictly separate from prospect-specific findings.
```

See `docs/architecture.md` for the full component map, data flow,
error model, and testing plan.

---

## Persistent Storage & Database Access (SQLite)

The system persists all pipeline artifacts to a local, relational SQLite database:

📁 **Database File Path:**  
`prospect-intelligence/data/prospect_intelligence.db`  
*(Absolute: `C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI\prospect-intelligence\data\prospect_intelligence.db`)*

### Opening with DB Browser for SQLite
You can inspect the entire database without any command-line SQL:
1. Download or open **DB Browser for SQLite** (free, open-source desktop app).
2. Click **File → Open Database...**
3. Navigate to and select `data/prospect_intelligence.db`.
4. Browse the **Database Structure**, **Browse Data**, or **Execute SQL** tabs.

### Relational Schema (6 Normalized Tables)
- `jobs` — Job lifecycle status, prospect inputs, timestamps, error tracking.
- `findings` — Individual discrete research findings with evidence labels (`Verified`, `Probable`, `Unverified`), field names, values, and source URLs.
- `lead_scores` — Deterministic 0–100 total scores, 5-tier priority bands (`A+ / Priority`, `A / Strong fit`, `B / Nurture`, `C / Low priority`, `D / Disqualify`), rubric version, and JSON breakdown.
- `briefs` — 11-section executive briefs with pain hypotheses, recommended approach, and source citations.
- `crm_exports` — HubSpot CRM payload exports (JSON & CSV formatted), contact mappings, and duplicate flags.
- `outreach_drafts` — Cold email cadences (Touch 1, 2, 3) and LinkedIn connection/pitch drafts.

### Pre-Written SQL Views (No SQL writing required)
The database includes 3 pre-built views:

1. **`vw_jobs_by_score_desc`** — All completed jobs ranked by lead score descending:
   ```sql
   SELECT * FROM vw_jobs_by_score_desc LIMIT 20;
   ```
2. **`vw_jobs_by_band`** — Aggregate summary stats per priority band:
   ```sql
   SELECT * FROM vw_jobs_by_band;
   ```
3. **`vw_failed_jobs`** — List of any failed jobs with error reasons:
   ```sql
   SELECT * FROM vw_failed_jobs;
   ```

---

## Requirements

- Python 3.11+
- An OpenAI API key (GPT-4o + text-embedding-3-small)
- A Serper.dev API key (web search)

---

## Installation

```bash
cd prospect-intelligence
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your keys:

```bash
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

Edit `.env`:

```
OPENAI_API_KEY=sk-...
SEARCH_API_KEY=...your-serper-key...
```

All other settings have working defaults for local development.

---

## Knowledge Base Setup

1. Export all 15 Coextend knowledge documents as PDFs:
   - 01 - Agent Instructions
   - 01 - Company Profile
   - 02 - Research Criteria
   - 02 - Services
   - 02 - LinkedIn Connection Messages
   - 03 - Company Capabilities
   - 03 - LinkedIn Pitch Messages
   - 03 - Marketing Strategy
   - 04 - Email Outreach
   - 04 - Research Output Template
   - 04 - Sales Positioning
   - 05 - Follow Up Messages
   - 05 - Ideal Customer Profile
   - 08 - Proposal Templates
   - Pilot Project Brief

2. Place them all in `data/knowledge_base/`

3. Ingest them:
   ```bash
   # After starting the server, call:
   curl -X POST http://localhost:8000/api/v1/knowledge/ingest
   # Or via the API docs at http://localhost:8000/docs
   ```

---

## Running the App

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 for the web UI, or http://localhost:8000/docs
for the interactive API documentation.

---

## Running Tests

```bash
pytest
```

Tests that do NOT require API keys (all unit + integration tests in this suite):
- `test_models.py` — schema validation
- `test_scoring.py` — all 10 scoring factors + repeatability
- `test_anti_fabrication.py` — missing-evidence handling
- `test_failure_injection.py` — bad URLs, malformed output
- `test_e2e_prospects.py` — 5 prospect archetypes (1 poor-fit, 2 ambiguous)
- `test_crm_adapter.py` — CRM export + duplicate detection

---

## Sample Input / Output

### Sample Input (API)
```json
POST /api/v1/prospects
{
  "company_name": "Harley Curtain Wall Ltd",
  "website": "https://www.harleycurtainwall.co.uk",
  "known_contact_name": "James Hargreaves",
  "known_contact_title": "Commercial Director"
}
```

### Sample Output (Job Created)
```json
{
  "job_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "status": "pending",
  "created_at": "2026-09-15T10:00:00",
  "company_name": "Harley Curtain Wall Ltd",
  "website": "https://www.harleycurtainwall.co.uk",
  "duplicate_warning": false
}
```

Poll `GET /api/v1/prospects/{job_id}` until `status` is `complete`,
then retrieve `GET /api/v1/prospects/{job_id}/brief`.

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/prospects` | Submit a prospect |
| GET | `/api/v1/prospects/{id}` | Job status |
| GET | `/api/v1/prospects/{id}/brief` | Research brief (`?format=markdown`) |
| GET | `/api/v1/prospects/{id}/crm-export` | CRM export (`?format=csv`) |
| POST | `/api/v1/prospects/{id}/outreach` | Generate outreach drafts |
| POST | `/api/v1/knowledge/ingest` | (Re)ingest knowledge base PDFs |
| GET | `/api/v1/health` | Liveness check |

Full interactive docs: http://localhost:8000/docs

---

## Known Limitations & Technical Debt

1. **In-process async worker** — background tasks run in the same process as
   the FastAPI server. Under high load, use Celery + Redis instead.

2. **SQLite** — appropriate for MVP/single-user; switch to Postgres for
   multi-user or production deployment.

3. **No authentication** — the API has no auth layer. Add OAuth2/API keys
   before any production deployment.

4. **LLM costs** — each research job consumes ~5,000–15,000 tokens for
   extraction + brief generation. See cost estimates below.

5. **Web scraping reliability** — some sites block automated fetching
   (JS-heavy SPAs, bot detection). A headless browser layer (Playwright)
   would improve coverage.

6. **Scoring rubric** — the 10-factor rubric uses keyword-matching heuristics.
   A more sophisticated classifier (fine-tuned or few-shot) would improve
   accuracy but add complexity.

7. **No human-in-the-loop review step** — the UI shows results but does not
   have an "approve/reject" workflow yet. That is a planned 60-day feature.

8. **Outreach quality** — message personalization quality depends on the depth
   of research findings. Richer findings from more sources → better drafts.

---

## Monthly Cost Estimate

Assumptions:
- Research extraction: ~8,000 tokens/job (GPT-4o input + output combined)
- Brief generation: ~6,000 tokens/job
- Outreach drafts (50% of jobs request): ~2,000 tokens/draft job
- Embeddings: ~30,000 tokens/job (query embeddings, 10 calls × 3,000 tokens avg)
- Web search: 5 queries/job × $0.001 = $0.005/job
- GPT-4o pricing: ~$5/1M input tokens, ~$15/1M output tokens (blended ~$8/1M)
- text-embedding-3-small: ~$0.02/1M tokens

| Volume | LLM Cost | Embeddings | Web Search | Total/month |
|--------|----------|------------|------------|-------------|
| 100 prospects/mo | ~$11 | ~$0.06 | ~$0.50 | **~$12** |
| 500 prospects/mo | ~$55 | ~$0.30 | ~$2.50 | **~$58** |
| 2,000 prospects/mo | ~$220 | ~$1.20 | ~$10.00 | **~$231** |

*Costs are estimates. Actual costs depend on page lengths, model version, and
outreach draft request rate. Monitor usage in the OpenAI and Serper dashboards.*

---

## 30/60/90-Day Roadmap

### 30 Days — Stabilise & Validate
- Deploy to a cloud instance (Railway / Render / AWS Lightsail)
- Add simple API key authentication
- Run against 20 real prospects; collect founder feedback on brief quality
- Tune scoring rubric based on real outcomes
- Add Postgres for multi-user support

### 60 Days — Enrich & Control
- Human-in-the-loop review UI: founder can approve/edit brief before
  it enters the CRM pipeline
- Batch prospect import (CSV upload)
- Live HubSpot integration (swap `MockHubSpotAdapter` for `LiveHubSpotAdapter`)
- Richer web research: LinkedIn public profiles (manual lookup, no automation)
- Evaluation-driven prompt tuning based on brief quality ratings

### 90 Days — Scale & Iterate
- Evaluation framework: score brief quality vs. actual deal outcomes
- Human-approved LinkedIn outreach queue (founder reviews and clicks send;
  system never sends autonomously — per Coextend's LinkedIn safety rule)
- Webhook / Zapier integration for CRM updates
- Dashboard: pipeline view of all prospects by band + status
- Cost monitoring and alerting
