# Design Document — Coextend Prospect Intelligence MVP

## Overview

The Coextend Prospect Intelligence MVP turns `{company_name, website, optional contact}` into a scored, cited, founder-ready research brief, plus a CRM-ready export and optional outreach drafts — delivered through one asynchronous pipeline per prospect.

The system has two strictly separated knowledge sources that never intermingle:

- **External Research Layer** — live web findings about *this specific prospect*, gathered fresh for every job.
- **Internal Knowledge Layer (RAG)** — Coextend's own 15 PDF documents (services, ICP, templates, capabilities), ingested once into ChromaDB and retrieved with citations whenever the system needs to talk about Coextend's own positioning.

Scoring is **deterministic code, not an LLM call**. The LLM's job is extraction, summarisation, and drafting. A pure scoring function (`scoring/engine.py`) owns the number.

---

## Architecture

### Full Pipeline Flowchart

```mermaid
flowchart TD
    UI[Minimal Web UI\nJinja2 + polling] -->|POST /api/v1/prospects| API[FastAPI service\napi/routes.py]
    API --> JobSvc[Job Service\napi/job_service.py]
    JobSvc -->|asyncio.create_task| Pipeline[Async Pipeline\npending → researching → scoring → drafting → complete]

    Pipeline --> RE[Research Engine\nengine/researcher.py]
    RE -->|5 search queries| Search[(Serper.dev\nweb search)]
    RE -->|fetch top 6 pages| Web[(Public web)]
    RE -->|LLM structured extraction| OpenAI1[(GPT-4o\nJSON schema mode)]
    RE --> Findings[(ResearchFindings\nper-job, SQLite)]

    Findings --> Scorer[Scoring Engine\nscoring/engine.py\npure function, no LLM]
    Scorer --> LeadScore[(LeadScore\n0-100, band, breakdown)]

    Findings --> BriefGen[Brief Generator\nengine/brief_generator.py]
    LeadScore --> BriefGen
    KB[(Knowledge Index\nChromaDB coextend_knowledge)] -->|top-k retrieved chunks\nwith citations| BriefGen
    BriefGen -->|LLM JSON schema call| OpenAI2[(GPT-4o\nJSON schema mode)]
    BriefGen --> Brief[(ResearchBrief\nSQLite blob)]

    Brief --> CRMAdapter[CRM Export Adapter\nMockHubSpotAdapter]
    CRMAdapter -->|duplicate check| CRMSample[(sample_crm.json)]
    CRMAdapter --> Exports[(data/exports/\n{job_id}_crm.json + .csv)]

    Brief --> OutreachGen[Outreach Generator\nengine/outreach_generator.py]
    KB -->|message templates| OutreachGen
    OutreachGen -->|LLM JSON schema call| OpenAI3[(GPT-4o\nJSON schema mode)]
    OutreachGen --> Drafts[(OutreachDrafts\nSQLite blob)]

    API -->|GET /prospects/{id}/brief| Brief
    API -->|GET /prospects/{id}/crm-export| Exports
    API -->|POST /prospects/{id}/outreach| OutreachGen
    API --> UI

    PDFs[Coextend PDFs\ndata/knowledge_base/] -->|POST /knowledge/ingest| Ingest[Ingestion pipeline\nknowledge/ingestion.py]
    Ingest -->|embed + upsert| KB
```

### Why the Two Knowledge Sources Must Stay Separate

The architectural separation between the external Research Engine and the internal Knowledge Index is not a convention — it is a correctness guarantee.

If prospect-specific web findings were mixed into the ChromaDB collection, the system could retrieve a *different* prospect's data when answering questions about a new prospect, silently polluting the brief with fabricated or misattributed facts. Conversely, if Coextend's own internal documents were injected into `ResearchFindings`, the scoring engine could award points based on what Coextend believes about a prospect rather than what was actually found on the web.

**How the code enforces this separation:**

1. `knowledge/ingestion.py` is the *only* writer to the `coextend_knowledge` ChromaDB collection. The research engine has no import of or dependency on `knowledge/`.
2. `engine/researcher.py` has an explicit module-level comment: *"This module ONLY produces prospect-specific findings. It NEVER reads from or writes to the internal knowledge index."*
3. `knowledge/retrieval.py` is scoped exclusively to `COLLECTION_NAME = "coextend_knowledge"` — it cannot reach prospect data because prospect data is never written there.
4. The `ResearchFindings` model (`api/models.py`) has no field for knowledge-base content; the `Brief_Generator` receives findings and KB chunks as **separate named inputs** in the prompt (`INPUT A` vs `INPUT C`), making it explicit in the LLM's context which source each fact came from.

---

## Component Responsibilities

| Component | Module | Responsibility | Must NOT do |
|---|---|---|---|
| **Research Engine** | `engine/researcher.py` | Execute 5 web search queries via Serper.dev; fetch up to 6 pages; use GPT-4o (JSON schema mode) to extract `ResearchFindings` with per-claim `EvidenceLabel` and `SourceRef` objects; fill scoring-relevant fields | Read from or write to `Knowledge_Index`; invent facts without source URLs; produce empty findings silently |
| **Knowledge Index (RAG)** | `knowledge/ingestion.py`, `knowledge/retrieval.py` | Ingest Coextend PDFs into `coextend_knowledge` ChromaDB collection (heading-aware chunking, ~600-token chunks, ~2400 chars max); embed via `text-embedding-3-small`; return top-k `KnowledgeChunk` objects with `source_document`, `section`, `page`, `score` | Store prospect-specific findings; be queried by the Research Engine |
| **Scoring Engine** | `scoring/engine.py`, `scoring/rubric.py` | Pure function `score(findings) → LeadScore`; evaluate 10 rubric factors using keyword-matching rules; sum to 0–100; assign band; record `rubric_version` | Make LLM calls; perform I/O; produce randomness; modify `EvidenceLabel` values |
| **Brief Generator** | `engine/brief_generator.py` | Combine `ResearchFindings` + `LeadScore` + retrieved KB chunks into `ResearchBrief` via GPT-4o (JSON schema mode); run post-generation label-escalation check; revert silently upgraded labels | Upgrade evidence labels; invent facts; use KB chunks as prospect facts |
| **CRM Export Adapter** | `api/crm_adapter.py` | `CRMAdapter` abstract interface + `MockHubSpotAdapter` implementation; map `ResearchBrief` to HubSpot-style JSON/CSV; write to `data/exports/`; duplicate-check against `sample_crm.json` | Make outbound HTTP calls to any CRM API; write to a live CRM |
| **Outreach Generator** | `engine/outreach_generator.py` | On-demand: retrieve message-library templates from KB; fill with Verified/Probable findings only via GPT-4o; return `OutreachDrafts` with `status="draft"` locked | Send or schedule any message; use `Unverified` findings as stated facts; perform LinkedIn actions |
| **API** | `api/routes.py`, `api/job_service.py` | FastAPI router: job lifecycle endpoints, brief/export/outreach retrieval; `job_service.py` orchestrates the async pipeline via `asyncio.create_task`; keeps all business logic out of routes | Contain business logic; perform research or scoring itself |
| **UI** | `ui/templates/`, `main.py` | Jinja2 server-rendered pages (`/` form, `/results/{job_id}` polling view); poll `GET /api/v1/prospects/{job_id}` every 5 seconds (configurable 3–30 s) for up to 300 s; display score, band, top 3 pain-point hypotheses, and recommended action | Require JavaScript frameworks; contain business logic |
| **Database** | `api/database.py` | SQLite via SQLAlchemy 2.x async + aiosqlite; `JobRow` ORM model; `init_db()` on startup; CRUD helpers (`create_job`, `get_job`, `update_job_status`, `save_json_field`, `find_recent_job`) | Store secrets or PII beyond what is needed for the job record |
| **Configuration** | `config.py` | `pydantic-settings` `Settings` class; loads all values from `.env` or OS environment; single `settings` singleton | Hard-code any API key or secret value |

---

## Data Models

All models are defined in `api/models.py` using **Pydantic v2**. They are the single source of truth for validation, serialisation, API documentation, and LLM JSON schema generation.

### ProspectRequest

```python
class ProspectRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    website: AnyHttpUrl                       # must have http or https scheme
    known_contact_name: str | None = Field(None, max_length=255)
    known_contact_title: str | None = Field(None, max_length=255)

    @field_validator("company_name")
    def strip_company_name(cls, v): return v.strip()
```

Validation: `company_name` is stripped of leading/trailing whitespace. `website` must be a well-formed URL with `http` or `https` scheme (enforced by Pydantic's `AnyHttpUrl`).

### JobStatus (enum)

```python
class JobStatus(str, Enum):
    PENDING      = "pending"
    RESEARCHING  = "researching"
    SCORING      = "scoring"
    DRAFTING     = "drafting"
    COMPLETE     = "complete"
    FAILED       = "failed"
```

### JobRecord

```python
class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    company_name: str
    website: str
    duplicate_warning: bool = False
    error_message: str | None = None
```

Returned immediately after `POST /api/v1/prospects`. The `error_message` field is populated when `status=failed`.

### EvidenceLabel (enum)

```python
class EvidenceLabel(str, Enum):
    VERIFIED   = "Verified"    # ≥2 SourceRef objects support the claim
    PROBABLE   = "Probable"    # exactly 1 SourceRef supports the claim
    UNVERIFIED = "Unverified"  # 0 SourceRef objects (inferred or uncertain)
```

This label travels through the entire pipeline on every `Finding` object. It is **never upgraded** — only the `Research Engine` assigns initial labels, and the post-generation check in `Brief_Generator` actively reverts any escalations.

### SourceRef

```python
class SourceRef(BaseModel):
    url: AnyHttpUrl
    title: str | None = None
    date_reviewed: date | None = None
```

Attached to every `Verified` or `Probable` finding. The `date_reviewed` field is set to `date.today()` at extraction time.

### Finding

```python
class Finding(BaseModel):
    field: str           # logical field name, e.g. "trade_fit", "company_size_band"
    value: str           # the extracted value string
    label: EvidenceLabel
    sources: list[SourceRef] = Field(default_factory=list)
```

The atomic unit of evidence in the system. The `field` name is the same string the Scoring Engine looks up via `_get_finding_value()`.

### ResearchFindings

```python
class ResearchFindings(BaseModel):
    job_id: str
    company_snapshot: list[Finding] = Field(default_factory=list)
    decision_makers: list[Finding]  = Field(default_factory=list)
    projects_signals: list[Finding] = Field(default_factory=list)
    notes_missing: list[str]        = Field(default_factory=list)
```

The output of the Research Engine. `notes_missing` is an explicit list of sections or scoring fields for which no evidence was found — never silently omitted. The Research Engine ensures all 10 scoring-relevant fields are present (populating `"no evidence found"` with `EvidenceLabel.UNVERIFIED` if absent).

**The 10 scoring-relevant fields extracted:**
`trade_fit`, `geography`, `company_size_band`, `tender_volume_signal`, `estimating_need_signal`, `drafting_bim_need_signal`, `hiring_trigger`, `decision_maker_access`, `outsourcing_readiness`, `commercial_attractiveness`

### ScoreFactor

```python
class ScoreFactor(BaseModel):
    factor: str
    weight: int = Field(..., ge=0, le=100)   # max points for this factor
    points_awarded: int = Field(..., ge=0)
    evidence: str                             # "[field_name] = 'extracted_value'"
```

### LeadScore

```python
class LeadScore(BaseModel):
    rubric_version: str                       # e.g. "v1.0"
    total: int = Field(..., ge=0, le=100)
    band: Literal["High", "Medium", "Low"]    # see band thresholds below
    breakdown: list[ScoreFactor]              # one entry per factor
```

**Band thresholds** (defined in `scoring/rubric.py`):

| Band | Threshold |
|---|---|
| High | total ≥ 70 |
| Medium | total ≥ 40 |
| Low | total < 40 |

Note: The requirements document specifies Hot/Warm/Cool/Cold terminology in some places; the implemented code and Pydantic model use `High/Medium/Low` (three bands). The `rubric_version` string (`"v1.0"`) is stored with every score so historical scores remain attributable to the rubric version that produced them.

### RecommendedApproach

```python
class RecommendedApproach(BaseModel):
    summary: str
    angle: str | None = None
    key_capabilities_to_lead_with: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
```

`knowledge_sources` contains the `source_document` names from the KB chunks that grounded this recommendation — the citation chain from RAG retrieval to the brief.

### NextAction

```python
class NextAction(BaseModel):
    action: str
    owner: str | None = None
    notes: str | None = None
```

### ResearchBrief

```python
class ResearchBrief(BaseModel):
    job_id: str
    snapshot: dict                              # key company facts
    contact: dict                               # decision-maker details
    company_research: dict                      # deeper background
    projects_signals: list[Finding]
    likely_requirements: list[Finding]
    pain_point_hypotheses: list[Finding]
    lead_score: LeadScore
    recommended_approach: RecommendedApproach
    risks_unknowns: list[str]
    next_action: NextAction
    sources: list[SourceRef]                    # all SourceRefs from findings
    generated_at: datetime = Field(default_factory=datetime.utcnow)
```

Note: A `validation_skipped: bool = False` flag should be added to this model (per Requirement 10.7) to indicate when the post-generation label-escalation check failed to execute due to a system error. In the current implementation, the check runs inline in `generate_brief()` and reverts labels silently with a warning log; a future iteration should surface this as a model field.

### OutreachDrafts

```python
class OutreachDrafts(BaseModel):
    job_id: str
    email_subject: str
    email_body: str
    linkedin_message: str
    status: Literal["draft"] = "draft"          # locked — cannot be changed
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    review_note: str = "draft — requires human review before use"
```

The `status` field is a `Literal["draft"]` — Pydantic rejects any attempt to set it to any other value. This is enforced at the model layer: `test_failure_injection.py::TestMalformedOutputHandling::test_outreach_draft_status_locked` verifies this with a `pytest.raises(ValidationError)` assertion.

### CRMExportRecord

```python
class CRMExportRecord(BaseModel):
    job_id: str
    company_fields: dict      # HubSpot company properties
    contact_fields: dict      # HubSpot contact properties
    deal_fields: dict         # HubSpot deal properties
    lead_score_total: int = Field(..., ge=0, le=100)
    lead_score_band: str
    possible_duplicate: bool = False
    exported_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Language** | Python 3.11+ | `from __future__ import annotations` throughout |
| **Web framework** | FastAPI | Async, auto-generates OpenAPI docs at `/docs` and `/redoc` |
| **Data validation** | Pydantic v2 | All models; `pydantic-settings` for configuration |
| **ASGI server** | Uvicorn | `uvicorn main:app --reload` for development |
| **Async jobs** | `asyncio.create_task` | Fire-and-forget in-process; swappable for Celery/RQ |
| **Database** | SQLite + SQLAlchemy 2.x async | `aiosqlite` driver; `sqlite+aiosqlite:///./data/prospect_intelligence.db` |
| **Vector store** | ChromaDB (`PersistentClient`) | File-based at `./data/vector_store`; cosine distance |
| **LLM** | OpenAI GPT-4o | `response_format={"type":"json_schema", "strict":True}` mode; `temperature=0` for extraction and briefs, `0.3` for outreach |
| **Embeddings** | OpenAI `text-embedding-3-small` | Batched in groups of 100; used for both KB ingestion and retrieval queries |
| **Web search** | Serper.dev (`/search` endpoint) | 5 queries per job, 8 results per query |
| **HTTP client** | `httpx` (async) | `follow_redirects=True`; 20-second timeout |
| **Retry/backoff** | `tenacity` | `@retry` decorators on `web_search` and `fetch_page` |
| **UI templates** | Jinja2 (`fastapi.templating`) | Server-rendered HTML; no JavaScript framework |
| **PDF extraction** | `pypdf` | Per-page text extraction; graceful fallback on corrupt files |
| **Config** | `pydantic-settings` | `.env` file or OS environment variables; no hard-coded secrets |
| **Testing** | `pytest`, `pytest-asyncio` | 108 tests; no live API keys required |

---

## API Surface

All endpoints are mounted under the `/api/v1` prefix. Full interactive documentation is available at `/docs` (Swagger UI) and `/redoc` (ReDoc).

| Method | Path | Status Codes | Description |
|---|---|---|---|
| `POST` | `/api/v1/prospects` | 202, 422 | Submit a new prospect. Returns `JobRecord` immediately; pipeline runs async. |
| `GET` | `/api/v1/prospects/{job_id}` | 200, 404 | Poll for job status. Returns current `JobRecord` including `status` and `error_message`. |
| `GET` | `/api/v1/prospects/{job_id}/brief` | 200, 404, 409 | Retrieve completed `ResearchBrief`. `?format=markdown` returns Markdown; default is JSON. 409 if job not yet complete. |
| `GET` | `/api/v1/prospects/{job_id}/crm-export` | 200, 404, 409 | Retrieve CRM export. `?format=csv` returns CSV with `Content-Disposition` attachment header; default is JSON. |
| `POST` | `/api/v1/prospects/{job_id}/outreach` | 200, 404, 409 | Generate outreach drafts on demand. Returns cached `OutreachDrafts` if already generated. 409 if job not complete. |
| `POST` | `/api/v1/knowledge/ingest` | 200 | (Re)ingest all PDFs from `data/knowledge_base/`. Returns `{"status":"ok","chunks_indexed":N}`. Safe to re-call; atomically replaces the collection. |
| `GET` | `/api/v1/health` | 200 | Liveness check. Returns `{"status":"ok"}`. |

### Request Validation

All request bodies are validated by Pydantic v2 models. Invalid requests return HTTP 422 with a structured error body containing `loc`, `msg`, and `type` fields matching the Pydantic v2 error schema. Unhandled exceptions never surface as bare stack traces — FastAPI's exception handling returns structured JSON with `error_code` and `message` fields.

### Duplicate Cooldown

When `POST /api/v1/prospects` is received, `job_service.py` calls `find_recent_job()` which queries SQLite for any existing job with the same `company_name` and `website` submitted within the last 24 hours (configurable via `settings.duplicate_cooldown_hours`). If found, `duplicate_warning=true` is set in the response; the request is not rejected.

---

## Deterministic Scoring Engine

### Design Principles

The Scoring Engine (`scoring/engine.py`) is a **pure function**: given identical `ResearchFindings` input within the same session, it always returns an identical `LeadScore`. There is no LLM call, no I/O, no randomness. This is the explicit contract tested by `test_score_repeatability` in `test_scoring.py`.

```python
def score(findings: ResearchFindings) -> LeadScore:
    ...
```

`_get_finding_value(findings, field_name)` searches all three finding lists (`company_snapshot`, `decision_makers`, `projects_signals`) for the named field, returning `"no evidence found"` if absent — which causes every scoring function to return 0 points.

### The 10 Rubric Factors

Defined in `scoring/rubric.py` as a list of `RubricFactor` dataclasses. Weights sum to exactly 100 (enforced by an `assert` at module load time).

| Factor name | Finding field | Max weight | Scoring logic |
|---|---|---|---|
| `trade_service_fit` | `trade_fit` | 20 | 20: facade/cladding/roofing/façade; 15: curtain wall/glazing; 10: building envelope/exterior/aluminium; 5: general contractor; 0: no evidence |
| `geography` | `geography` | 10 | 10: UK/US/Canada; 5: Australia/Ireland/UAE/Singapore/New Zealand; 0: elsewhere or no evidence. Word-boundary regex prevents `australia` from matching `us`. Expansion markets checked first. |
| `company_size_capacity` | `company_size_band` | 10 | Extracts first integer from value string. 10: 50–500; 5: 10–49; 3: >500; 0: no number found or "no evidence" |
| `tender_project_volume` | `tender_volume_signal` | 15 | 15: multiple/framework/active/high volume/several; 8: tender/bid/project/pipeline; 0: no evidence |
| `estimating_need` | `estimating_need_signal` | 10 | 10: estimat/take-off/takeoff/qs/quantity survey/bq/boq; 5: growing/expansion/recruit; 0: no evidence |
| `drafting_bim_need` | `drafting_bim_need_signal` | 10 | 10: shop drawing/bim/drafting/revit/autocad/tekla; 5: design/technical/engineering; 0: no evidence |
| `hiring_capacity_trigger` | `hiring_trigger` | 10 | 10: estimat/bim/drafting/shop draw/take-off; 5: hiring/recruit/vacancy/job/growing team; 0: no evidence |
| `decision_maker_access` | `decision_maker_access` | 5 | 5: managing director/commercial director/estimating director/pre-construction/technical director/procurement/qs director; 2: director/manager/head of; 0: no evidence |
| `outsourcing_readiness` | `outsourcing_readiness` | 5 | 5: outsourc/subcontract/offshore/external resource; 2: capaci/stretch/busy/growing; 0: no evidence |
| `commercial_attractiveness` | `commercial_attractiveness` | 5 | 5: £/$/ million/m turnover/award/prestige/tier 1; 2: contract/revenue/commercial; 0: no evidence |

### Rubric Version

`RUBRIC_VERSION = "v1.0"` is stored in every `LeadScore`. When scoring logic changes, this string must be bumped. Past scores in the database remain attributable to the version that produced them.

### Zero-Evidence Safety

When `_get_finding_value` returns `"no evidence found"`, every `_*_score()` function checks for that string first and returns 0. If all finding lists are empty, all 10 factors score 0, `total=0`, `band="Low"`. This is the "refuses to invent" guarantee for scoring.

---

## RAG / Knowledge Index Design

### Ingestion Pipeline (`knowledge/ingestion.py`)

1. **PDF discovery**: glob `*.pdf` and `*.PDF` in `settings.knowledge_base_path` (`./data/knowledge_base/`).
2. **Text extraction**: `pypdf.PdfReader` per file, per-page, returns `[{page: int, text: str}]`. Corrupt or unreadable PDFs are skipped with a warning log — ingestion continues for remaining files.
3. **Heading-aware chunking** (`_split_into_chunks`):
   - Detects headings via regex: Markdown-style `# Heading` or ALL-CAPS lines of 5+ characters.
   - Splits text at heading boundaries first, preserving `section` metadata per chunk.
   - Hard-splits oversized segments: `MAX_CHARS_PER_CHUNK = 2400` chars (~600 tokens), with `OVERLAP_CHARS = 100` between consecutive chunks.
   - Each chunk carries `{text, source_document, section, page, chunk_index}`.
4. **Embedding**: `text-embedding-3-small` via OpenAI API, batched in groups of 100.
5. **Atomic replacement**: delete the existing `coextend_knowledge` collection, recreate it, upsert all new chunks in batches of 500. If the process fails partway through, ChromaDB retains the previous state because the delete/recreate is effectively transactional at the collection level.
6. **Empty directory handling**: if no PDFs found, returns 0 with a warning log and HTTP 200.

### Retrieval (`knowledge/retrieval.py`)

- `retrieve(query, top_k=5)` embeds the query string with `text-embedding-3-small`, queries ChromaDB with cosine distance, returns up to `top_k` `KnowledgeChunk` objects.
- `KnowledgeChunk` fields: `text`, `source_document`, `section`, `page`, `score` (cosine similarity 0–1, derived as `1.0 - distance`).
- Returns empty list (never raises) if the collection does not exist or the vector store is unavailable — the `Brief_Generator` handles empty retrieval by populating sections with `"No relevant internal knowledge available"`.
- `format_chunks_for_prompt(chunks)` renders each chunk as:
  ```
  [N] Source: 'source_document' | Section: 'section' | Page: N
  <chunk text>
  ```
  This labelled format is what the LLM sees as `INPUT C`.

### Citation Chain

Every call to `format_chunks_for_prompt` tags each chunk with its `source_document`. The Brief Generator system prompt instructs the LLM to list cited document names in `recommended_approach.knowledge_sources`. This creates a traceable path from a statement in the brief back to the specific Coextend PDF it came from.

### Prompt Labelling

When the Brief Generator builds its LLM prompt, it explicitly separates the three inputs:

```
INPUT A — Research Findings:
<ResearchFindings JSON>

INPUT B — Lead Score:
<LeadScore JSON>

INPUT C — Internal Knowledge (cite source document names):
[1] Source: '03 - Company Capabilities' | Section: 'Services' | Page: 4
...
```

The system prompt states: *"A fact about the PROSPECT must come from Input A only. A fact about COEXTEND'S services, capabilities, ICP, or approach must come from Input C only."*

---

## Brief and Outreach Generation

### Brief Generator (`engine/brief_generator.py`)

**Process:**

1. Extract company name from `ResearchFindings.company_snapshot`.
2. Execute 4 KB queries to retrieve internal knowledge (Coextend services, ICP, recommended approach, value proposition). Deduplicate chunks by text; pass up to 12 unique chunks to the LLM.
3. Build the structured prompt (system + user with 3 named inputs).
4. Call GPT-4o with `response_format={"type":"json_schema","json_schema":{"strict":True,...}}` and `temperature=0`.
5. On `json.JSONDecodeError`, append the error to the user message and retry once.
6. Parse raw dict → `ResearchBrief` via `_build_brief()`.
7. Run `_validate_no_label_upgrade(findings, brief)` — see post-generation check below.
8. Return `ResearchBrief`.

**JSON Schema (`_BRIEF_SCHEMA`):** Covers all 9 LLM-generated sections (`snapshot`, `contact`, `company_research`, `projects_signals`, `likely_requirements`, `pain_point_hypotheses`, `recommended_approach`, `risks_unknowns`, `next_action`). The schema sets `"additionalProperties": False` to prevent the LLM from adding extraneous fields. The `lead_score` and `sources` sections are injected programmatically from the already-computed `LeadScore` and original `SourceRef` objects — never left to the LLM to generate.

**[EVIDENCE MISSING] Handling:**

The system prompt instructs the LLM: *"If a section has no evidence, say 'No evidence found'"*. Requirement 10.2 mandates the marker string `[EVIDENCE MISSING]` followed by the section name. These two conventions should be unified in a future iteration. Currently, the system prompt uses `"No evidence found"` phrasing; the requirements specify `"[EVIDENCE MISSING]"`.

### Post-Generation Label-Escalation Check (`_validate_no_label_upgrade`)

After generation, the function:

1. Builds a dict `{field: label}` from all original findings.
2. For every `Finding` in `projects_signals`, `likely_requirements`, and `pain_point_hypotheses` in the brief:
   - If the original finding was `Probable` or `Unverified` and the brief finding is `Verified`, that is an escalation.
   - The label is **silently reverted** to the original label.
   - A warning is logged: `"Evidence label upgrade detected and reverted for fields: [...]"`.

The revert-rather-than-crash approach keeps the pipeline running while preserving correctness. Per Requirement 10.3, a future iteration should also transition the job to `failed:label_upgrade_violation` instead of silently reverting.

### Outreach Generator (`engine/outreach_generator.py`)

**Process:**

1. Filter safe findings: only `Verified` or `Probable` items from `projects_signals` and `likely_requirements`, plus snapshot facts (`company_name`, `location`, `sector`, `size`).
2. Retrieve message-library KB chunks (3 queries, up to 8 unique chunks).
3. Call GPT-4o with `temperature=0.3` (slight variation for natural-sounding copy).
4. Validate output: `_assert_no_unverified_facts()` checks if any `Unverified` finding's value appears verbatim in the draft bodies. Logs a warning if detected; does not crash the pipeline.
5. Return `OutreachDrafts` with `status="draft"` locked and `review_note` pre-populated.

**Four-part message structure** (enforced via system prompt):

1. Observation — a specific Verified/Probable prospect fact.
2. Likely problem — a hypothesis, framed as such.
3. Relevant capability — from internal knowledge, with citation.
4. Low-friction next step — a simple ask.

**Constraints:**
- Email body: < 200 words.
- LinkedIn message: ≤ 300 characters.
- `Unverified` findings are never used as stated facts.
- No send/schedule capability exists anywhere in the codebase.

---

## Job Status Machine and Error Handling

### Status Transitions

```
pending
  └─→ researching   (Research Engine starts)
        └─→ scoring        (Scoring Engine runs)
              └─→ drafting       (Brief Generator starts)
                    └─→ complete       (CRM export done)

Any stage → failed:<reason>
```

All transitions are written to SQLite via `update_job_status()`. The `error_message` column stores the reason string (max 1024 characters per Requirement 1.8).

The pipeline orchestrator (`_run_pipeline` in `job_service.py`) wraps all steps in a single `try/except Exception`. Any unhandled exception transitions the job to `failed` with `reason = f"{type(exc).__name__}: {exc}"`.

### Named `failed:` Reason Codes

| Reason code | Trigger |
|---|---|
| `failed:insufficient_web_data` | All web search queries exhausted with errors (Req. 2.9) |
| `failed:research_engine_unavailable` | Research Engine startup fails after 2 retries (Req. 2.10) |
| `failed:incomplete_brief` | Brief Generator output is missing one or more of the 11 required sections (Req. 5.1) |
| `failed:missing_label` | Post-generation validation detects a claim without an `EvidenceLabel` (Req. 5.2) |
| `failed:brief_timeout` | Brief generation exceeds 120 seconds from entering `status=drafting` (Req. 5.9) |
| `failed:llm_parse_error` | Both LLM attempts return malformed JSON (Req. 5.7, 9.5) |
| `failed:label_escalation` | Post-generation check detects a label upgrade (currently: silently reverts; future: raise) |
| `failed:label_upgrade_violation` | Formal rejection path for label escalation (Req. 10.3 target) |

### Retry and Backoff

Retry logic is handled by **tenacity** decorators in `engine/web_utils.py`:

```python
@retry(
    wait=wait_exponential(multiplier=1.5, min=1, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
async def web_search(query: str, ...) -> list[dict]: ...

@retry(...)
async def fetch_page(url: str) -> str: ...
```

- **Base delay:** 1.5 seconds (`settings.backoff_base_seconds`).
- **Max delay:** 30 seconds.
- **Attempts:** 3 (`settings.max_retries`).
- **Conditions:** any `httpx.HTTPError` or `httpx.TimeoutException`.
- **After exhaustion:** `reraise=True` propagates the final exception to the caller.

HTTP timeout per request is 20 seconds (`_TIMEOUT`).

### LLM Re-Prompt on Malformed JSON

Both `researcher.py` and `brief_generator.py` wrap their LLM calls in a `for attempt in range(2)` loop:

- Attempt 0: normal call.
- On `json.JSONDecodeError`: append `"\n\nPREVIOUS RESPONSE HAD A JSON ERROR: {exc}\nPlease return valid JSON only."` to the user message.
- Attempt 1: retry with augmented prompt.
- On second failure: `raise RuntimeError("llm_parse_error: ...")`, which transitions the job to `failed:llm_parse_error`.

This matches Requirement 9.4: one automatic re-prompt within 10 seconds of detecting non-conformance.

### Structured Error Responses

All HTTP 4xx and 5xx responses from FastAPI include a structured JSON body. Pydantic v2 validation errors return:

```json
{
  "detail": [
    {"loc": ["body", "website"], "msg": "invalid or missing URL scheme", "type": "url_scheme"}
  ]
}
```

Custom 404/409/500 responses use `HTTPException` with a `detail` string. No unhandled Python exception is ever surfaced as a bare stack trace to API clients.

---

## Testing Strategy

### Test Suite Overview

108 tests across 6 test files, all runnable without live API keys:

```
pytest prospect-intelligence/
```

| Test file | What it validates |
|---|---|
| `tests/test_models.py` | Pydantic v2 schema validation: required fields, URL validation, enum constraints, field stripping, locked `status="draft"`, score range bounds |
| `tests/test_scoring.py` | All 10 scoring factor functions independently; band assignment; full `score()` function; **score-repeatability test** (Req. 4.4) |
| `tests/test_anti_fabrication.py` | Empty findings → all-zero scores; `"no evidence found"` value → 0 points; label immutability (scoring engine must not alter labels); ambiguous size → 0 points; partial information → other factors remain 0 |
| `tests/test_failure_injection.py` | Bad URL rejection; missing required fields; `LeadScore.total > 100` rejected; invalid `EvidenceLabel` rejected; `OutreachDrafts.status="sent"` rejected; tenacity `@retry` decorator presence; simulated retry-then-succeed flow |
| `tests/test_e2e_prospects.py` | 5 prospect archetypes via mocked findings: P1 high-fit (UK facade, ≥70), P2 poor-fit (software/Germany, ≤15), P3 ambiguous (general contractor/Canada, 15–60), P4 partial (ambiguous size → 0 for size factor), P5 expansion (Australia, geography=5); rubric version consistency; score repeatability across all 5 |
| `tests/test_crm_adapter.py` | JSON and CSV file creation; `possible_duplicate=False` on empty sample; duplicate detection by company name; duplicate detection by domain; score band in export |

### Key Named Tests

**`test_score_repeatability` (test_scoring.py)**: Scores the same `ResearchFindings` twice and asserts `total`, `band`, `rubric_version`, and every per-factor `points_awarded` are identical. This is the explicit automated guarantee of Requirement 4.4.

**`test_score_repeatability_all_prospects` (test_e2e_prospects.py)**: Extends the repeatability check across all 5 realistic prospect archetypes.

**`test_empty_findings_notes_missing_not_crash` (test_anti_fabrication.py)**: The "refuses to invent" test for scoring. Constructs `ResearchFindings` with no findings at all and asserts every factor awards 0 points.

**`test_no_evidence_value_scores_zero` (test_anti_fabrication.py)**: Constructs findings where every scoring field has `value="no evidence found"`, asserting `total=0` and `band="Low"`.

**`test_outreach_draft_status_locked` (test_failure_injection.py)**: Asserts that `OutreachDrafts(status="sent")` raises `ValidationError` — the model-layer enforcement that the system can never mark a draft as sent.

### Testing Approach

- **Unit tests**: specific examples and edge cases, especially error conditions.
- **No live API calls**: all tests that would require Serper.dev or OpenAI use mocked `ResearchFindings` objects constructed directly.
- **Async tests**: `pytest-asyncio` for CRM adapter tests that use `async def`.
- **tmp_path isolation**: CRM adapter tests use `pytest`'s `tmp_path` fixture to avoid touching real export directories.

### Dual Testing Approach (Property-Based Testing Assessment)

The Scoring Engine (`scoring/engine.py` + `scoring/rubric.py`) is the primary candidate for property-based testing: it is a pure function with no I/O, and its correctness properties hold across a wide input space. A future iteration should add a property-based test library (e.g., `hypothesis`) to verify:

- For any `ResearchFindings`, `score(findings).total` is always in `[0, 100]`.
- For any `ResearchFindings`, `score(findings)` called twice returns identical results.
- For any `ResearchFindings` where all values are `"no evidence found"`, `score(findings).total == 0`.

Other components (research extraction, brief generation, outreach generation) involve LLM I/O and are not suitable for property-based testing. The CRM adapter and API layer are best covered by example-based integration tests.

---

## Security and Compliance

### Secrets Management

All secrets are loaded exclusively from environment variables or a `.env` file via `pydantic-settings`. The `config.py` module provides a single `settings` singleton; no API key or credential value is hard-coded anywhere in the source. The `.env` file is listed in `.gitignore`.

Configuration values:

```env
OPENAI_API_KEY=sk-...
SEARCH_API_KEY=...your-serper-key...
```

All other settings have safe defaults for local development.

### No LinkedIn Automation

The system has no LinkedIn scraping, connection-request, or messaging capability — not as a prompt-level restriction, but because **no such code path exists**. The `Outreach_Generator` generates draft text only. The `OutreachDrafts.status` field is locked to `"draft"` at the model layer. Requirement 7.5–7.6 is enforced by absence, not by guard clauses.

### No Live CRM Writes

`MockHubSpotAdapter` is the only concrete `CRMAdapter` implementation. It writes exclusively to local files in `data/exports/`. The `CRMAdapter.export()` interface intentionally has no `base_url` or `api_key` parameters in the mock — there is no code path that would make an outbound HTTP call to HubSpot. Requirement 6.8 is enforced structurally.

### PII Handling

Contact names and titles (`known_contact_name`, `known_contact_title` from `ProspectRequest`) are stored in the `jobs` SQLite table and may be included in the `ResearchBrief.contact` dict and `CRMExportRecord.contact_fields`. No personal data beyond what is operationally necessary for the brief and CRM export is stored. There is no scraping of personal social-media profiles.

### Authentication

The MVP API has no authentication layer. Before any deployment beyond a local machine, API key authentication or OAuth2 must be added (noted in the 30-day roadmap).

### Input Validation

All API request bodies are validated by Pydantic v2 before any processing begins. URL scheme (`http`/`https` only) and length constraints are enforced at the model layer, not ad-hoc in route handlers.

---

## Cost Estimation

Based on the following assumptions per research job:

- Research extraction: ~8,000 tokens (GPT-4o input + output combined).
- Brief generation: ~6,000 tokens.
- Outreach drafts (50% of jobs): ~2,000 tokens per draft job.
- Embeddings: ~30,000 tokens per job (10 query embedding calls, average 3,000 tokens each).
- Web search: 5 queries × $0.001 = $0.005 per job.
- GPT-4o pricing: ~$5/1M input tokens, ~$15/1M output tokens (blended ~$8/1M).
- `text-embedding-3-small`: ~$0.02/1M tokens.

| Volume | LLM Cost | Embeddings | Web Search | **Total/month** |
|---|---|---|---|---|
| 100 prospects/month | ~$11 | ~$0.06 | ~$0.50 | **~$12** |
| 500 prospects/month | ~$55 | ~$0.30 | ~$2.50 | **~$58** |
| 2,000 prospects/month | ~$220 | ~$1.20 | ~$10.00 | **~$231** |

Costs are estimates. Actual costs depend on page lengths and content richness, model version, and the proportion of jobs that request outreach drafts. Monitor usage in the OpenAI and Serper dashboards.

---

## 30/60/90-Day Roadmap

### 30 Days — Stabilise and Validate

- Deploy to a cloud instance (Railway / Render / AWS Lightsail).
- Add simple API key authentication to all endpoints.
- Run against 20 real prospects; collect founder feedback on brief quality.
- Tune scoring rubric based on real-world outcomes; bump `RUBRIC_VERSION` to `"v1.1"`.
- Switch to Postgres for multi-user or production support.

### 60 Days — Enrich and Control

- **Human-in-the-loop review UI**: founder can approve or edit the brief before it enters the CRM pipeline. This is the planned stage for the `validation_skipped` flag to become meaningful.
- Batch prospect import via CSV upload.
- **Live HubSpot integration**: implement `LiveHubSpotAdapter` behind the `CRMAdapter` interface, with an environment flag to switch from mock to live. No changes to the pipeline orchestrator.
- Richer web research: LinkedIn public profile lookup (manual lookup workflow only — no automated scraping).
- Evaluation-driven prompt tuning based on brief quality ratings.

### 90 Days — Scale and Iterate

- Evaluation framework: score brief quality against actual deal outcomes to close the feedback loop.
- **Human-approved LinkedIn outreach queue**: the founder reviews drafts in-UI and clicks send. The system never sends autonomously — this is an explicit compliance constraint per Coextend's LinkedIn safety rule.
- Webhook / Zapier integration for CRM status updates.
- Pipeline dashboard: view all prospects by band and status, sortable and filterable.
- Cost monitoring and alerting based on token usage per job.
- Property-based test suite for the Scoring Engine using `hypothesis`.

---

## Known Limitations and Technical Debt

1. **In-process async worker** — background tasks run inside the FastAPI process via `asyncio.create_task`. Under concurrent load, a long research job will compete with API request handling. Production path: Celery + Redis worker pool.

2. **SQLite** — appropriate for single-user MVP. Switch to Postgres before multi-user or production deployment.

3. **No authentication** — the API has no auth layer. All endpoints are open. Add API key authentication before any external deployment.

4. **Label revert rather than fail** — the post-generation label-escalation check in `_validate_no_label_upgrade` reverts labels silently with a warning log. Requirement 10.3 specifies transitioning to `failed:label_upgrade_violation`. This is technically debt.

5. **`[EVIDENCE MISSING]` marker** — Requirement 10.2 specifies the exact string `"[EVIDENCE MISSING]"` as a section placeholder. The system prompt currently uses `"No evidence found"` phrasing. These should be unified.

6. **`validation_skipped` flag** — Requirement 10.7 specifies a `validation_skipped=true` flag on `ResearchBrief` when the post-generation check cannot run. This field is not yet in the Pydantic model.

7. **Web scraping reliability** — JavaScript-heavy SPAs and bot-detection will cause `fetch_page` to return minimal content or fail all retries. A headless browser layer (Playwright) would improve coverage.

8. **Scoring rubric accuracy** — the 10-factor rubric uses keyword-matching heuristics. A fine-tuned or few-shot classifier would improve precision for ambiguous cases.

9. **No human review step** — the UI shows results but has no approve/reject workflow. Planned for the 60-day milestone.

10. **Outreach quality ceiling** — message personalization depth is limited by the depth of the research findings. Richer findings (more source pages fetched, better extraction) produce better drafts.
