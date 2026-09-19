# Architecture Note — Coextend Prospect Intelligence MVP

## Purpose

Turn `{company name, website, optional contact}` into a scored, cited,
founder-ready research brief, a CRM-ready export, and optional outreach drafts
— via one asynchronous pipeline per prospect.

---

## Component Map

```
┌──────────────────────────────────────────────────────────────┐
│  Web UI  (Jinja2 + vanilla-JS polling)                       │
│  /  → form submission                                        │
│  /results/{job_id} → status polling + results display       │
└────────────────────┬─────────────────────────────────────────┘
                     │ POST /api/v1/prospects
                     ▼
┌──────────────────────────────────────────────────────────────┐
│  FastAPI Service  (api/)                                     │
│  • Input validation (Pydantic v2)                            │
│  • Job lifecycle:  pending→researching→scoring→              │
│                    drafting→complete | failed:<reason>       │
│  • Swagger UI: /docs   ReDoc: /redoc                         │
│  • No business logic — thin routing layer only               │
└────────┬────────────────────────────┬────────────────────────┘
         │ asyncio.create_task        │ reads/writes
         ▼                            ▼
┌────────────────────┐   ┌──────────────────────────────────┐
│  Research Engine   │   │  SQLite (SQLAlchemy async)        │
│  engine/researcher │   │  api/database.py                 │
│  • 5 web search    │   │  • JobRow ORM model              │
│    queries         │   │  • JSON blob columns for         │
│  • fetch top-6     │   │    findings, brief, export,      │
│    pages           │   │    outreach                      │
│  • GPT-4o JSON     │   └──────────────────────────────────┘
│    extraction      │
│  → ResearchFindings│
└────────┬───────────┘
         │                ┌────────────────────────────────┐
         │                │  Knowledge Index (ChromaDB)    │
         │                │  knowledge/                    │
         │                │  • Coextend PDFs ONLY          │
         │                │  • Heading-aware chunks        │
         │                │    (~600 tokens / 2400 chars)  │
         │                │  • Embedded: text-embedding-   │
         │                │    3-small                     │
         │                │  • Collection: coextend_       │
         │                │    knowledge                   │
         │                │  • top-k retrieval + citations │
         │                └────────────┬───────────────────┘
         │                             │ cited chunks (INPUT C)
         ▼                             │
┌────────────────────┐                 │
│  Scoring Engine    │                 │
│  scoring/engine.py │                 │
│  • Pure function — │                 │
│    no LLM, no I/O  │                 │
│  • 10-factor rubric│                 │
│  → LeadScore       │                 │
└────────┬───────────┘                 │
         │ (INPUT B)                   │
         ▼◄────────────────────────────┘
┌────────────────────────────────────────────────────────────┐
│  Brief Generator  engine/brief_generator.py                │
│  • INPUT A: ResearchFindings (prospect facts only)         │
│  • INPUT B: LeadScore                                      │
│  • INPUT C: KB chunks [Internal: <source_document>]        │
│  • GPT-4o, temperature=0, JSON schema strict mode         │
│  • Post-generation label-escalation check                  │
│  • lead_score + sources injected programmatically          │
│  → ResearchBrief                                           │
└────────┬───────────────────────────────────────────────────┘
         │
         ├──────────────────────────────┐
         ▼                              ▼
┌────────────────────┐   ┌─────────────────────────────────┐
│  Outreach Draft    │   │  CRM Export Adapter             │
│  Generator         │   │  api/crm_adapter.py             │
│  engine/outreach_  │   │  MockHubSpotAdapter             │
│  generator.py      │   │  • maps brief → company_fields, │
│  • on demand only  │   │    contact_fields, deal_fields  │
│  • Verified /      │   │  • writes JSON + CSV to         │
│    Probable only   │   │    data/exports/                │
│  • GPT-4o, temp    │   │  • duplicate check against      │
│    = 0.3           │   │    sample_crm.json              │
│  → OutreachDrafts  │   └─────────────────────────────────┘
│    status="draft"  │
│    (model-locked)  │
└────────────────────┘
```

---

## Data Flow (per research job)

1. **Intake** — `POST /api/v1/prospects` validates `ProspectRequest` via
   Pydantic v2, creates a `JobRow` in SQLite (`status=pending`), fires
   `asyncio.create_task(_run_pipeline(job_id))`, and returns `JobRecord`
   with `job_id` within 500 ms.

2. **Research** (`status=researching`) — Research Engine executes 5 Serper.dev
   queries, fetches up to 6 pages via async `httpx`, calls GPT-4o in JSON
   schema mode to extract `ResearchFindings`. Every material claim receives an
   `EvidenceLabel` (`Verified` ≥ 2 `SourceRef`, `Probable` = 1, `Unverified`
   = 0). All 10 scoring-relevant fields are guaranteed present (absent fields
   filled with `"no evidence found"` + `EvidenceLabel.UNVERIFIED`).

3. **Scoring** (`status=scoring`) — Pure function `score(findings)` applies
   the 10-factor ICP rubric using keyword-matching rules. No LLM, no I/O, no
   randomness. Produces `LeadScore` (0–100, band, breakdown, rubric_version).

4. **Brief generation** (`status=drafting`) — Brief Generator retrieves up to
   12 de-duplicated KB chunks via 4 semantic queries, builds a three-input
   prompt, calls GPT-4o with JSON schema strict mode. Runs
   `_validate_no_label_upgrade()` post-generation to revert any escalated
   labels. `lead_score` and `sources` are injected programmatically.

5. **CRM export** — `MockHubSpotAdapter.export(brief)` maps the brief to
   HubSpot-style fields, writes `{job_id}_{slug}.json` and
   `{job_id}_{slug}.csv` to `data/exports/`. Duplicate check against
   `sample_crm.json` by normalised `company_name` and website domain.

6. **Complete** (`status=complete`) — brief, score, and export all accessible
   via GET endpoints.

7. **Outreach (on demand)** — `POST /api/v1/prospects/{id}/outreach` retrieves
   message-library templates from ChromaDB (3 queries, up to 8 unique chunks),
   filters findings to `Verified`/`Probable` only, calls GPT-4o at
   temperature=0.3. Returns `OutreachDrafts` with `status="draft"` locked at
   model layer. Cached on first call.

---

## Knowledge Separation (enforced structurally)

The separation between the external Research Layer and the internal Knowledge
Index is a correctness guarantee, not a convention.

| Store | Contains | Never contains |
|---|---|---|
| ChromaDB `coextend_knowledge` | Coextend PDFs only (services, ICP, rubric, templates, message libraries) | Prospect-specific `ResearchFindings` |
| SQLite `jobs` table | Per-job `ResearchFindings`, `ResearchBrief`, `CRMExportRecord`, `OutreachDrafts` as JSON blobs | Coextend internal documents |

**How the code enforces this:**

1. `knowledge/ingestion.py` is the **only** writer to `coextend_knowledge`.
   The research engine has no import of `knowledge/`.
2. `engine/researcher.py` has a module-level comment: *"This module ONLY
   produces prospect-specific findings. It NEVER reads from or writes to the
   internal knowledge index."*
3. `knowledge/retrieval.py` is scoped exclusively to
   `COLLECTION_NAME = "coextend_knowledge"`.
4. The `ResearchFindings` model has no field for KB content. The Brief
   Generator receives findings and KB chunks as separate named inputs
   (`INPUT A` vs `INPUT C`) in the LLM prompt.

---

## Error Model

### Job Status Machine

```
pending
  └─→ researching   (Research Engine starts)
        └─→ scoring        (Scoring Engine runs)
              └─→ drafting       (Brief Generator starts)
                    └─→ complete       (CRM export done)

Any stage → failed:<reason>
```

All transitions written to SQLite via `update_job_status()`. The
`error_message` column stores the reason string (max 1024 characters).

### Named `failed:` Reason Codes

| Reason code | Trigger |
|---|---|
| `failed:insufficient_web_data` | All web search queries exhausted with errors |
| `failed:research_engine_unavailable` | Research Engine startup fails after 2 retries |
| `failed:incomplete_brief` | Brief Generator output is missing ≥ 1 of the 11 required sections |
| `failed:missing_label` | Post-generation validation detects a claim without an `EvidenceLabel` |
| `failed:brief_timeout` | Brief generation exceeds 120 seconds from entering `status=drafting` |
| `failed:llm_parse_error` | Both LLM attempts return malformed JSON (researcher or brief generator) |
| `failed:label_escalation` | Post-generation check detects an evidence-label upgrade (currently reverts; future: raise) |
| `failed:label_upgrade_violation` | Formal rejection path for label escalation (Req. 10.3 target) |

### Retry and Backoff

Applied via `tenacity @retry` in `engine/web_utils.py`:

- **Conditions:** any `httpx.HTTPError` or `httpx.TimeoutException`
- **Attempts:** 3 (`settings.max_retries`)
- **Wait:** `wait_exponential(multiplier=1.5, min=1, max=30)`
- **After exhaustion:** `reraise=True` propagates to caller

Non-critical step failure (one query, one page fetch): logged, appended to
`ResearchFindings.notes_missing`, pipeline continues.

Critical step failure: job transitions to `failed:<reason>` within 5 seconds
of the final retry.

### LLM Re-Prompt on Malformed JSON

Both `researcher.py` and `brief_generator.py` use a `for attempt in range(2)`
loop. On `json.JSONDecodeError`, the error and original schema are appended to
the user message and the LLM is called once more. If the second attempt also
fails, `RuntimeError("llm_parse_error: ...")` is raised → `failed:llm_parse_error`.

### Structured Error Responses (Req. 9.7)

All HTTP 4xx and 5xx responses include a JSON body with:
- `error_code`: non-empty string
- `message`: human-readable string, ≤ 500 characters

Pydantic v2 validation errors (HTTP 422) include `loc`, `msg`, and `type`
fields per the Pydantic v2 error schema. No unhandled Python exception is ever
surfaced as a bare stack trace to API clients.

---

## API Surface

All endpoints mounted under `/api/v1`. Interactive docs at `/docs` (Swagger)
and `/redoc` (ReDoc).

| Method | Path | Status Codes | Description |
|---|---|---|---|
| `POST` | `/api/v1/prospects` | 202, 422 | Submit prospect; async pipeline fires |
| `GET` | `/api/v1/prospects/{job_id}` | 200, 404 | Poll job status |
| `GET` | `/api/v1/prospects/{job_id}/brief` | 200, 404, 409 | Get `ResearchBrief`; `?format=markdown` |
| `GET` | `/api/v1/prospects/{job_id}/crm-export` | 200, 404, 409 | Get CRM export; `?format=csv` |
| `POST` | `/api/v1/prospects/{job_id}/outreach` | 200, 404, 409 | Generate / return cached outreach drafts |
| `POST` | `/api/v1/knowledge/ingest` | 200 | (Re)ingest PDFs from `data/knowledge_base/` |
| `GET` | `/api/v1/health` | 200 | Liveness check: `{"status": "ok"}` |

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.11+ | `from __future__ import annotations` throughout |
| Web framework | FastAPI | Async, auto-generates `/docs` and `/redoc` |
| Data validation | Pydantic v2 | All models; `pydantic-settings` for config |
| ASGI server | Uvicorn | `uvicorn main:app --reload` for development |
| Async jobs | `asyncio.create_task` | Fire-and-forget in-process; swappable for Celery |
| Database | SQLite + SQLAlchemy 2.x async | `aiosqlite` driver |
| Vector store | ChromaDB `PersistentClient` | File-based at `./data/vector_store`; cosine distance |
| LLM | OpenAI GPT-4o | `response_format={"type":"json_schema","strict":True}`; `temperature=0` for extraction and briefs, `0.3` for outreach |
| Embeddings | OpenAI `text-embedding-3-small` | Batched in groups of 100 |
| Web search | Serper.dev `/search` | 5 queries per job, 8 results per query |
| HTTP client | `httpx` async | `follow_redirects=True`; 20-second timeout |
| Retry/backoff | `tenacity` | `@retry` on `web_search` and `fetch_page` |
| UI templates | Jinja2 (`fastapi.templating`) | Server-rendered HTML; no JS framework |
| PDF extraction | `pypdf` | Per-page text; graceful fallback on corrupt files |
| Config | `pydantic-settings` | `.env` or OS environment; no hard-coded secrets |
| Testing | `pytest`, `pytest-asyncio` | 108 tests; no live API keys required |

---

## Deterministic Scoring Engine

The Scoring Engine (`scoring/engine.py`) is a **pure function**:

```python
def score(findings: ResearchFindings) -> LeadScore: ...
```

- No LLM calls, no I/O, no randomness.
- `RUBRIC_VERSION = "v1.0"` stored in every `LeadScore`.
- `_get_finding_value(findings, field)` searches all three finding lists;
  returns `"no evidence found"` if absent → 0 points for that factor.
- Band thresholds: `High` ≥ 70, `Medium` ≥ 40, `Low` < 40.
- Weights sum to exactly 100 (enforced by `assert` at module load).

### 10 Rubric Factors

| Factor | Finding field | Max pts |
|---|---|---|
| `trade_service_fit` | `trade_fit` | 20 |
| `geography` | `geography` | 10 |
| `company_size_capacity` | `company_size_band` | 10 |
| `tender_project_volume` | `tender_volume_signal` | 15 |
| `estimating_need` | `estimating_need_signal` | 10 |
| `drafting_bim_need` | `drafting_bim_need_signal` | 10 |
| `hiring_capacity_trigger` | `hiring_trigger` | 10 |
| `decision_maker_access` | `decision_maker_access` | 5 |
| `outsourcing_readiness` | `outsourcing_readiness` | 5 |
| `commercial_attractiveness` | `commercial_attractiveness` | 5 |

---

## Testing Plan

### Test Files

| File | What it validates |
|---|---|
| `tests/test_models.py` | Pydantic v2 schema: required fields, URL scheme, enum constraints, `company_name` strip, `status="draft"` lock, score range bounds |
| `tests/test_scoring.py` | All 10 factor functions independently; band assignment at boundary values; `score()` function; score-repeatability (Req. 4.4) |
| `tests/test_anti_fabrication.py` | Empty findings → all-zero scores; `"no evidence found"` → 0 pts; label immutability in scoring; ambiguous size → 0 pts; partial info → other factors remain 0 |
| `tests/test_failure_injection.py` | Bad URL rejection; missing required fields; `LeadScore.total > 100` rejected; invalid `EvidenceLabel`; `OutreachDrafts.status="sent"` rejected; tenacity `@retry` decorator presence; retry-then-succeed flow |
| `tests/test_e2e_prospects.py` | 5 prospect archetypes (mocked findings): P1 high-fit UK facade ≥70, P2 poor-fit software/Germany ≤15, P3 ambiguous general contractor/Canada 15–60, P4 partial ambiguous size → 0 size factor, P5 expansion Australia geography=5; rubric version consistency; repeatability across all 5 |
| `tests/test_crm_adapter.py` | JSON + CSV file creation; `possible_duplicate=False` on empty sample; duplicate detection by name and domain; score band in export |

### Key Named Tests

- **`test_score_repeatability`** (`test_scoring.py`): scores identical
  `ResearchFindings` twice, asserts `total`, `band`, `rubric_version`, and
  every `points_awarded` are equal. Explicit automated guarantee for Req. 4.4.

- **`test_score_repeatability_all_prospects`** (`test_e2e_prospects.py`):
  extends repeatability across all 5 prospect archetypes.

- **`test_empty_findings_notes_missing_not_crash`** (`test_anti_fabrication.py`):
  constructs `ResearchFindings` with no findings; asserts every factor scores 0.

- **`test_no_evidence_value_scores_zero`** (`test_anti_fabrication.py`):
  all scoring fields set to `"no evidence found"` → `total=0`, `band="Low"`.

- **`test_outreach_draft_status_locked`** (`test_failure_injection.py`):
  `OutreachDrafts(status="sent")` raises `ValidationError` — model-layer
  enforcement that the system can never mark a draft as sent.

### Running Tests

```bash
# All tests (no live API keys required)
cd prospect-intelligence
pytest --tb=short

# With coverage
pytest --tb=short --cov=. --cov-report=term-missing
```

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| LLM invents prospect facts | Structured JSON schema + explicit prompt prohibition + evidence labels + `[EVIDENCE MISSING]` marker |
| LLM ignores evidence-label pass-through | `_validate_no_label_upgrade()` reverts any escalated label post-generation; logged as warning |
| Scoring non-determinism | Score is pure code, no LLM — deterministic by construction; `test_score_repeatability` enforces this |
| Vector store retrieves wrong collection | Separate ChromaDB collection names; retrieval scoped to `coextend_knowledge` only |
| Prospect data leaks into KB | `knowledge/ingestion.py` is the only writer to `coextend_knowledge`; no import of `knowledge/` in `engine/` |
| PDF chunking loses section context | Heading-aware chunking preserves `section` metadata per chunk (`MAX_CHARS=2400`, `OVERLAP=100`) |
| Rate limits / API timeouts | tenacity retry/backoff on every external call: 3 attempts, exponential base 1.5 s, max 30 s |
| JavaScript-heavy SPAs block fetch | `fetch_page` timeout = 20 s; failure appended to `notes_missing`; pipeline continues (non-critical) |
| Concurrent load saturates async worker | Single FastAPI process; production path: Celery + Redis worker pool |

---

## Known Technical Debt

1. **In-process async worker** — `asyncio.create_task` competes with request
   handling under load. Production path: Celery + Redis.
2. **SQLite** — single-user only. Switch to Postgres before multi-user or
   production deployment.
3. **No authentication** — all endpoints are open. Add API key auth before
   any external deployment.
4. **Label revert, not fail** — `_validate_no_label_upgrade` currently reverts
   labels silently. Req. 10.3 specifies `failed:label_upgrade_violation`.
5. **`[EVIDENCE MISSING]` marker** — Req. 10.2 specifies the exact string
   `"[EVIDENCE MISSING]"` but system prompt currently uses `"No evidence
   found"`. Should be unified.
6. **`validation_skipped` flag** — Req. 10.7 specifies a
   `validation_skipped=true` field on `ResearchBrief`; not yet in the Pydantic
   model.
7. **Web scraping reliability** — JavaScript SPAs and bot-detection cause
   `fetch_page` to return minimal content. Playwright headless browser would
   improve coverage.
8. **Scoring keyword heuristics** — 10-factor rubric uses keyword matching.
   A fine-tuned classifier would improve precision for ambiguous cases.
9. **No human review step** — the UI shows results but has no approve/reject
   workflow. Planned for the 60-day milestone.

---

## Secrets Management

All secrets are loaded from environment variables or a `.env` file via
`pydantic-settings`. No API key or credential value is hard-coded in source
files. The `.env` file is listed in `.gitignore`. See `.env.example` for all
required configuration keys with placeholder values.

```env
OPENAI_API_KEY=sk-...your-key-here...
SEARCH_API_KEY=...your-key-here...
```

---

## 30/60/90-Day Roadmap

### 30 Days — Stabilise and Validate
- Deploy to Railway / Render / AWS Lightsail
- Add API key authentication to all endpoints
- Run against 20 real prospects; collect founder feedback
- Tune scoring rubric; bump `RUBRIC_VERSION` to `"v1.1"`
- Switch to Postgres for multi-user support

### 60 Days — Enrich and Control
- Human-in-the-loop review UI (approve/edit brief before CRM push)
- Batch prospect import via CSV upload
- Live `HubSpotAdapter` behind the `CRMAdapter` interface (env flag to switch)
- Richer web research: LinkedIn public profile lookup (manual workflow only)
- Evaluation-driven prompt tuning from brief quality ratings

### 90 Days — Scale and Iterate
- Evaluation framework: score brief quality against deal outcomes
- Human-approved LinkedIn outreach queue (founder reviews drafts in-UI)
- Webhook / Zapier integration for CRM status updates
- Pipeline dashboard: all prospects by band and status
- Cost monitoring and alerting on token usage per job
- Property-based test suite for the Scoring Engine using `hypothesis`
