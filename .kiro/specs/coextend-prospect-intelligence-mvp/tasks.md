# Implementation Plan: Coextend Prospect Intelligence MVP

## Overview

Full incremental implementation plan for the Coextend Prospect Intelligence MVP. The project is substantially implemented in `prospect-intelligence/` with 113 passing tests. Tasks are listed as a complete TDD checklist — sub-tasks map to concrete files and functions so every requirement is traceable.

## Tasks

- [x] 1. Project scaffolding and architecture note
  - Initialise directory structure: `/api`, `/engine`, `/knowledge`, `/scoring`, `/tests`, `/data/knowledge_base`, `/data/exports`
  - Set up FastAPI app skeleton (`main.py`) with lifespan startup, Jinja2 template mounting, and `/api/v1` router prefix
  - Expose `GET /api/v1/health` endpoint returning `{"status": "ok"}`
  - Add `.env.example` with placeholders for `OPENAI_API_KEY` and `SEARCH_API_KEY` — no real secrets committed
  - Write `docs/architecture.md`: components, data-flow summary, risks, and test plan overview
  - _Requirements: 8.4, 9.7_

- [x] 2. Core data models
  - [x] 2.1 Implement `EvidenceLabel` enum (`Verified` / `Probable` / `Unverified`) in `api/models.py`
    - Define as `str, Enum` so it serialises cleanly through Pydantic v2 and JSON responses
    - _Requirements: 2.3, 4.1, 10.3_

  - [x] 2.2 Implement `SourceRef`, `Finding`, `ResearchFindings` models
    - `SourceRef`: `url: AnyHttpUrl`, `title: str | None`, `date_reviewed: date | None`
    - `Finding`: `field`, `value`, `label: EvidenceLabel`, `sources: list[SourceRef]`
    - `ResearchFindings`: `job_id`, `company_snapshot`, `decision_makers`, `projects_signals`, `notes_missing`
    - _Requirements: 2.2, 2.3, 2.7, 10.6_

  - [x] 2.3 Implement `ScoreFactor` and `LeadScore` models
    - `ScoreFactor`: `factor`, `weight`, `points_awarded`, `evidence`
    - `LeadScore`: `rubric_version`, `total` (0–100), `band` (`High`/`Medium`/`Low`), `breakdown: list[ScoreFactor]`
    - _Requirements: 4.1, 4.2, 4.4_

  - [x] 2.4 Implement `ProspectRequest`, `JobStatus` enum, and `JobRecord` models
    - `ProspectRequest`: `company_name` (1–255 chars, stripped), `website: AnyHttpUrl`, optional contact fields
    - `JobStatus`: `pending → researching → scoring → drafting → complete / failed`
    - `JobRecord`: `job_id`, `status`, `created_at`, `company_name`, `website`, `duplicate_warning`, `error_message`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 2.5 Implement `RecommendedApproach`, `NextAction`, `ResearchBrief`, and `OutreachDrafts` models
    - `ResearchBrief`: all 11 template sections including `knowledge_citations`; add `validation_skipped: bool = False` flag
    - `OutreachDrafts`: `status: Literal["draft"]` locked at model layer; `review_note` pre-populated
    - _Requirements: 5.1, 7.1, 10.7_

  - [x] 2.6 Implement `CRMExportRecord` model
    - `company_fields`, `contact_fields`, `deal_fields` dicts; `lead_score_total`, `lead_score_band`, `possible_duplicate`
    - _Requirements: 6.1, 6.7_

  - [x]* 2.7 Write schema validation unit tests (`tests/test_models.py`)
    - Test required fields, `AnyHttpUrl` scheme enforcement, enum constraints, `company_name` strip, `status="draft"` lock, score range bounds
    - _Requirements: 1.2, 1.3, 1.4, 7.5_

- [x] 3. Job intake and lifecycle
  - [x] 3.1 Implement SQLite database layer (`api/database.py`)
    - `JobRow` ORM model via SQLAlchemy 2.x async + `aiosqlite`
    - CRUD helpers: `create_job`, `get_job`, `update_job_status`, `save_json_field`, `find_recent_job`
    - `init_db()` called on FastAPI lifespan startup
    - _Requirements: 1.5, 1.7, 1.8_

  - [x] 3.2 Implement `POST /api/v1/prospects` route (`api/routes.py`)
    - Validate `ProspectRequest` via Pydantic v2; return HTTP 422 on invalid input with `loc`/`msg`/`type` fields
    - Create `JobRecord` with `status=pending`; return `job_id`, `status`, `created_at`, `company_name`, `website`, `duplicate_warning` within 500 ms
    - Fire `asyncio.create_task(_run_pipeline(job_id))` without awaiting
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 8.5_

  - [x] 3.3 Implement duplicate-submission cooldown check (`api/job_service.py`)
    - Call `find_recent_job()` for same `website` domain within preceding 24 hours
    - Set `duplicate_warning=true` in response; do not reject the request
    - Also check `company_name` (normalised: lowercased, trimmed, collapsed whitespace) against `sample_crm.json`
    - _Requirements: 1.9, 6.3, 6.4_

  - [x] 3.4 Implement `GET /api/v1/prospects/{job_id}` route
    - Return current `JobRecord`; HTTP 404 if `job_id` does not exist
    - _Requirements: 1.5, 1.6_

  - [x] 3.5 Implement job status state machine in `api/job_service.py`
    - `_run_pipeline`: `pending → researching → scoring → drafting → complete`; any exception → `failed:<reason>`
    - Wrap all pipeline steps in `try/except`; record reason string (≤ 1024 chars) via `update_job_status`
    - _Requirements: 1.7, 1.8, 9.2_

- [x] 4. Knowledge ingestion — internal RAG layer
  - [x] 4.1 Implement PDF text extraction and heading-aware chunking (`knowledge/ingestion.py`)
    - `pypdf.PdfReader` per page; detect headings via Markdown `# Heading` or ALL-CAPS regex
    - Split at heading boundaries; hard-split oversized segments: `MAX_CHARS_PER_CHUNK=2400`, `OVERLAP_CHARS=100`
    - Each chunk carries `{text, source_document, section, page, chunk_index}`
    - Skip corrupt/unreadable PDFs with a warning log; continue remaining files
    - _Requirements: 3.1, 3.8_

  - [x] 4.2 Implement embedding and vector store indexing
    - Embed chunks via `text-embedding-3-small` (OpenAI), batched in groups of 100
    - Store in ChromaDB `PersistentClient` collection `coextend_knowledge` with full metadata
    - _Requirements: 3.1, 3.2_

  - [x] 4.3 Implement atomic re-ingestion (`POST /api/v1/knowledge/ingest`)
    - Delete existing `coextend_knowledge` collection, recreate it, upsert all new chunks in batches of 500
    - If replacement fails mid-way, retain previous collection contents unchanged
    - Return `{"status": "ok", "chunks_indexed": N}`; return HTTP 200 with zero-chunks message if directory is empty
    - _Requirements: 3.7, 3.9_

  - [x] 4.4 Implement retrieval function (`knowledge/retrieval.py`)
    - `retrieve(query, top_k=5)` — embed query, cosine-distance search, return `list[KnowledgeChunk]`
    - Each `KnowledgeChunk`: `text`, `source_document`, `section`, `page`, `score` (0–1)
    - Return empty list (never raise) if collection absent or unavailable
    - Scope retrieval strictly to `coextend_knowledge`; never read prospect-specific data
    - _Requirements: 3.2, 3.3, 3.4_

  - [x] 4.5 Implement `format_chunks_for_prompt` helper
    - Render each chunk as `[N] Source: 'source_document' | Section: 'section' | Page: N\n<text>`
    - Used by `Brief_Generator` as `INPUT C` in the LLM prompt
    - _Requirements: 3.4, 3.5_

  - [x]* 4.6 Write grounding and citation test
    - Ask a known internal-knowledge question; assert the answer traces to the correct `source_document`
    - Verify no prospect-specific data is written to `coextend_knowledge`
    - _Requirements: 3.3, 3.5_

- [x] 5. External research engine
  - [x] 5.1 Implement web search and page-fetch utilities with retry/backoff (`engine/web_utils.py`)
    - `web_search(query)`: POST to Serper.dev `/search`; 5 queries per job, 8 results per query
    - `fetch_page(url)`: async `httpx` GET, `follow_redirects=True`, 20-second timeout
    - Apply `tenacity @retry`: `wait_exponential(multiplier=1.5, min=1, max=30)`, `stop_after_attempt(3)`, `reraise=True`
    - _Requirements: 2.5, 2.6, 9.1_

  - [x] 5.2 Implement structured extraction via LLM (`engine/researcher.py`)
    - Execute 5 web search queries; fetch top 6 pages; call GPT-4o (`temperature=0`, JSON schema mode)
    - Extract `ResearchFindings` with per-claim `EvidenceLabel` and `SourceRef` objects
    - Assign `Verified` (≥2 `SourceRef`), `Probable` (1 `SourceRef`), `Unverified` (0 `SourceRef`) per claim
    - Populate all 10 scoring-relevant fields; fill absent fields with `"no evidence found"` + `EvidenceLabel.UNVERIFIED`
    - Add explicit module-level comment: *"This module ONLY produces prospect-specific findings. It NEVER reads from or writes to the internal knowledge index."*
    - _Requirements: 2.1, 2.2, 2.3, 2.7, 2.8_

  - [x] 5.3 Implement `notes_missing` recording for absent evidence
    - When a research section has no web-source evidence, record its name in `ResearchFindings.notes_missing`
    - Never omit a section silently or fabricate content
    - _Requirements: 2.4, 9.3_

  - [x] 5.4 Handle terminal research failures
    - If every web-search query attempt fails, transition `Job` to `failed:insufficient_web_data`
    - If `Research_Engine` startup fails after 2 retries, transition to `failed:research_engine_unavailable`
    - _Requirements: 2.9, 2.10_

  - [x]* 5.5 Write research engine tests
    - Test 3+ sample prospects (via mocked findings): verify findings carry `SourceRef` URLs and correct `EvidenceLabel` assignments
    - Test `notes_missing` is populated when a section has no evidence
    - _Requirements: 2.2, 2.3, 2.4_

- [x] 6. Deterministic lead scoring engine
  - [x] 6.1 Implement scoring rubric configuration (`scoring/rubric.py`)
    - Define 10 `RubricFactor` dataclasses with weights summing to exactly 100 (enforced by `assert` at module load)
    - Set `RUBRIC_VERSION = "v1.0"`
    - Include keyword-matching rules per factor (see design table for `trade_service_fit` through `commercial_attractiveness`)
    - _Requirements: 4.1, 4.4_

  - [x] 6.2 Implement `_get_finding_value` helper (`scoring/engine.py`)
    - Search all three finding lists (`company_snapshot`, `decision_makers`, `projects_signals`) for a named field
    - Return `"no evidence found"` if absent — triggers 0 points in every scoring function
    - _Requirements: 4.5, 4.7_

  - [x] 6.3 Implement one scoring function per rubric factor
    - `_trade_service_fit_score`, `_geography_score`, `_company_size_score`, `_tender_volume_score`, `_estimating_need_score`, `_drafting_bim_need_score`, `_hiring_trigger_score`, `_decision_maker_access_score`, `_outsourcing_readiness_score`, `_commercial_attractiveness_score`
    - Each is a pure function; no LLM calls, no I/O, no randomness
    - Return 0 when value is `"no evidence found"`
    - _Requirements: 4.3, 4.6_

  - [x] 6.4 Implement `score(findings: ResearchFindings) -> LeadScore` pure function
    - Call all 10 factor functions; sum results; assign `band` (`High` ≥70, `Medium` ≥40, `Low` <40)
    - Populate `zero_evidence_factors` in `LeadScore` for any factor awarded 0 points due to absent fields
    - Attach `rubric_version` string to every returned `LeadScore`
    - _Requirements: 4.1, 4.2, 4.4, 4.5_

  - [x]* 6.5 Write scoring unit tests (`tests/test_scoring.py`, `tests/test_anti_fabrication.py`)
    - Unit-test each of the 10 factor functions independently with known input/output pairs, including the 0-points / no-evidence path
    - Test band assignment at boundary values (69, 70, 39, 40)
    - `test_score_repeatability`: score same `ResearchFindings` twice; assert `total`, `band`, `rubric_version`, and every per-factor `points_awarded` are identical
    - `test_empty_findings_notes_missing_not_crash`: all-empty findings → `total=0`, all 10 factors in `zero_evidence_factors`
    - `test_no_evidence_value_scores_zero`: all fields `"no evidence found"` → `total=0`, `band="Low"`
    - _Requirements: 4.3, 4.6, 4.7_

- [x] 7. Research brief generator
  - [x] 7.1 Implement JSON-schema-constrained LLM brief generation (`engine/brief_generator.py`)
    - Build three-input prompt: `INPUT A` (ResearchFindings JSON), `INPUT B` (LeadScore JSON), `INPUT C` (formatted KB chunks)
    - Call GPT-4o with `response_format={"type":"json_schema","strict":True}`, `temperature=0`
    - Schema covers all 9 LLM-generated sections; `lead_score` and `sources` injected programmatically
    - `"additionalProperties": False` on schema to prevent extraneous fields
    - _Requirements: 5.1, 5.7, 10.1_

  - [x] 7.2 Enforce prompt-level knowledge-source separation
    - System prompt must state: *"A fact about the PROSPECT must come from Input A only. A fact about COEXTEND's services, capabilities, ICP, or approach must come from Input C only."*
    - Label each KB chunk as `[Internal: <source_document>]` in the prompt
    - Build `knowledge_citations` list mapping statements to their `source_document` and `section`
    - _Requirements: 3.4, 3.5, 5.5_

  - [x] 7.3 Implement evidence-label pass-through and post-generation validation
    - `_validate_no_label_upgrade(findings, brief)`: build `{field: label}` dict from original findings; revert any escalated label; log warning
    - System prompt must prohibit inventing company names, project names, contact details, revenue figures
    - Populate sections with `"[EVIDENCE MISSING] <section_name>"` when no evidence available (per Req 10.2)
    - Set `validation_skipped=True` on `ResearchBrief` if the check cannot run (per Req 10.7)
    - _Requirements: 5.2, 5.3, 5.8, 10.2, 10.3, 10.7_

  - [x] 7.4 Implement LLM re-prompt on malformed JSON and brief timeout
    - `for attempt in range(2)` loop: on `json.JSONDecodeError`, append schema + error to user message and retry
    - On second failure: raise `RuntimeError("llm_parse_error: ...")` → transition `Job` to `failed:llm_parse_error`
    - Enforce 120-second timeout from `status=drafting`; on expiry transition to `failed:brief_timeout`
    - _Requirements: 5.7, 5.9, 9.4, 9.5_

  - [x] 7.5 Implement `GET /api/v1/prospects/{job_id}/brief` endpoint
    - Return `ResearchBrief` as JSON by default; Markdown when `?format=markdown` supplied
    - Return HTTP 404 if no brief exists for the given `job_id`
    - _Requirements: 5.6_

  - [x]* 7.6 Write brief generator tests (`tests/test_anti_fabrication.py`)
    - `test_empty_findings_no_fabrication`: all empty findings → every factual section contains `"[EVIDENCE MISSING]"`, no generated claims
    - `test_no_label_upgrade_on_output`: brief with escalated labels is reverted, not passed through
    - Test `knowledge_citations` list traces to correct `source_document`
    - _Requirements: 5.2, 5.3, 10.2, 10.3, 10.4_

- [x] 8. CRM export adapter
  - [x] 8.1 Define `CRMAdapter` abstract interface (`api/crm_adapter.py`)
    - Abstract base class with `export(brief: ResearchBrief) -> CRMExportRecord`
    - Interface must have no `base_url` or `api_key` parameters to structurally prevent live CRM calls
    - _Requirements: 6.7, 6.8_

  - [x] 8.2 Implement `MockHubSpotAdapter`
    - Map `ResearchBrief` to HubSpot-style `company_fields`, `contact_fields`, `deal_fields`
    - Enforce field length limits: `recommended_approach` ≤ 280 chars, `next_action` ≤ 280 chars, `sources_summary` ≤ 500 chars (URL list format)
    - Write both `.json` and `.csv` files to `data/exports/` using `{job_id}_{company_name_slug}.{ext}` pattern
    - Filename slug: lowercase, non-alphanumeric → hyphen, collapse consecutive hyphens, truncate at 60 chars; overwrite if exists
    - _Requirements: 6.1, 6.2_

  - [x] 8.3 Implement duplicate detection against `sample_crm.json`
    - Normalise `company_name`: lowercase, strip leading/trailing whitespace, collapse internal whitespace to single space
    - Set `duplicate_warning=true` if match found; set `duplicate_warning=false` with `duplicate_check_warning` note if file absent or unparseable
    - _Requirements: 6.3, 6.4_

  - [x] 8.4 Implement `GET /api/v1/prospects/{job_id}/crm-export` endpoint
    - Return JSON export by default; CSV with `Content-Disposition: attachment` when `?format=csv`
    - HTTP 404 with structured error body if no export file exists for the given `job_id` and format
    - _Requirements: 6.5, 6.6_

  - [x]* 8.5 Write CRM adapter tests (`tests/test_crm_adapter.py`)
    - Test JSON and CSV file creation with correct filename slug
    - Test `possible_duplicate=False` on empty sample CRM
    - Test duplicate detection by `company_name` (normalised) and by `website` domain
    - Test `lead_score_band` present in export
    - _Requirements: 6.2, 6.3, 6.5_

- [x] 9. Outreach draft generator
  - [x] 9.1 Implement outreach draft generation (`engine/outreach_generator.py`)
    - Filter findings to `Verified` / `Probable` only from `projects_signals` and `likely_requirements` plus snapshot snapshot facts
    - Retrieve message-library KB chunks (3 queries, up to 8 unique chunks deduplicated by text)
    - Call GPT-4o with `temperature=0.3`; enforce four-part message structure via system prompt
    - Enforce length limits: email body < 200 words, LinkedIn message ≤ 300 characters
    - _Requirements: 7.1, 7.3_

  - [x] 9.2 Enforce draft integrity and anti-automation constraints
    - `status: Literal["draft"]` locked at model layer; `review_note` pre-populated
    - `_assert_no_unverified_facts()`: check if any `Unverified` finding value appears verbatim in draft bodies; log warning
    - No send, schedule, or submit capability anywhere in this code path
    - _Requirements: 7.4, 7.5, 7.6_

  - [x] 9.3 Handle empty templates and no verified findings
    - If no matching message-library templates in `Knowledge_Index`: return `OutreachDrafts` with empty bodies and `notes` field explaining absence
    - If no `Verified` or `Probable` claims: return `OutreachDrafts` with empty bodies and `notes` field; still set `draft_status="draft"`
    - _Requirements: 7.7, 7.9_

  - [x] 9.4 Implement `POST /api/v1/prospects/{job_id}/outreach` endpoint
    - Return HTTP 409 if job `status` is not `complete`
    - Return HTTP 404 if `job_id` does not exist
    - Return cached `OutreachDrafts` if already generated for this job
    - _Requirements: 7.2, 7.8_

  - [x]* 9.5 Write outreach generator tests
    - `test_outreach_draft_status_locked`: assert `OutreachDrafts(status="sent")` raises `ValidationError`
    - `test_no_unverified_facts_in_drafts`: build findings with `Unverified` claims; assert draft bodies contain no verbatim `Unverified` text
    - _Requirements: 7.3, 7.5, 10.5_

- [x] 10. Minimal web UI
  - [x] 10.1 Implement prospect submission form (`ui/templates/index.html`)
    - Form fields: `company_name` (required), `website` (required), optional `known_contact_name`, `known_contact_title`
    - Inline validation: if `company_name` or `website` empty on submit, display inline error and do NOT submit request
    - On submit: call `POST /api/v1/prospects`, display returned `job_id` and initial `status`
    - _Requirements: 8.1_

  - [x] 10.2 Implement job-status polling and results view (`ui/templates/results.html`)
    - Poll `GET /api/v1/prospects/{job_id}` at configurable interval (default 5 s, min 3 s, max 30 s) for up to 300 s
    - Display timeout error and stop polling if status remains non-terminal after 300 s
    - On `status=complete`: display company name, lead score and band, top 3 pain-point hypotheses, and recommended outreach action
    - Update display on next poll cycle without additional delay
    - _Requirements: 8.2, 8.3_

  - [x] 10.3 Surface failure states in plain language
    - Parse `failed:<reason>` and display human-readable message in UI
    - Map all named reason codes to user-facing descriptions
    - _Requirements: 8.2_

- [x] 11. Logging, reliability, and end-to-end evaluation
  - [x] 11.1 Add structured JSON logging throughout
    - Every API request, `Job` status transition, external call attempt, retry, and failure
    - Required fields: `job_id`, `timestamp`, `level`, `message`
    - Never log secret values (API keys); log key names only
    - _Requirements: 8.6_

  - [x] 11.2 Apply retry/backoff wrapper to all external calls (`engine/web_utils.py`)
    - Centralise `tenacity @retry` decorator: `wait_exponential(multiplier=1.5, min=1, max=30)`, `stop_after_attempt(3)`
    - Apply to `web_search`, `fetch_page`, and all LLM API calls
    - Non-critical step failure (single query/fetch): log, append to `notes_missing`, continue pipeline
    - Critical step failure: transition `Job` to `failed:<reason>` within 5 s of final retry
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 11.3 Implement LLM JSON re-prompt on malformed output
    - Single automatic re-prompt with original schema + specific validation error included in user message
    - If second attempt also fails: transition `Job` to `failed:llm_parse_error`
    - _Requirements: 9.4, 9.5_

  - [x] 11.4 Implement structured error responses for all 4xx and 5xx
    - All error responses must include `error_code` (non-empty string) and `message` (≤ 500 chars)
    - Unhandled exceptions must never surface as bare stack traces
    - _Requirements: 9.7_

  - [x]* 11.5 Write failure-injection and end-to-end tests
    - `test_failure_injection.py`: bad URL rejection, missing required fields, `LeadScore.total > 100` rejected, invalid `EvidenceLabel` rejected, `OutreachDrafts.status="sent"` rejected, tenacity `@retry` decorator presence, simulated retry-then-succeed flow
    - `test_e2e_prospects.py`: 5 prospect archetypes via mocked findings — P1 high-fit (UK facade ≥70), P2 poor-fit (software/Germany ≤15), P3 ambiguous (general contractor/Canada 15–60), P4 partial (ambiguous size → 0 for size factor), P5 expansion (Australia, geography=5); rubric version consistency; score repeatability across all 5
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [x] 12. Documentation and delivery package
  - [x] 12.1 Write `README.md`: installation, configuration, architecture summary, and run instructions
    - Include `pip install -r requirements.txt`, `.env` setup, `uvicorn main:app --reload`, and `pytest` commands
    - _Requirements: 8.7_

  - [x] 12.2 Verify `docs/architecture.md` Mermaid diagram renders correctly
    - Confirm all components, data-flow arrows, and technology labels are accurate against the implemented code
    - _Requirements: (delivery)_

  - [x] 12.3 Provide `.env.example` and sample input/output files
    - `.env.example`: all configuration keys with placeholder values, no real secrets
    - At least 2 sample `ResearchFindings` JSON files representing distinct prospect archetypes
    - _Requirements: 8.7_

  - [x] 12.4 Document known limitations and technical debt
    - In-process async worker, SQLite single-user constraint, no authentication, label-revert-not-fail, `[EVIDENCE MISSING]` marker inconsistency, missing `validation_skipped` field, web-scraping SPA limitations, scoring keyword heuristics, no human review step
    - _Requirements: (delivery)_

  - [x] 12.5 Write monthly cost estimate
    - Calculate at 100 / 500 / 2,000 prospects/month with stated assumptions (token counts, GPT-4o pricing, embedding cost, Serper.dev per-query cost)
    - _Requirements: (delivery)_

  - [x] 12.6 Write 30/60/90-day roadmap
    - 30 days: cloud deploy, API key auth, 20-prospect validation run, rubric tuning
    - 60 days: human-in-the-loop review UI, batch CSV import, live HubSpot adapter, evaluation-driven prompt tuning
    - 90 days: evaluation framework, founder-approved LinkedIn outreach queue, webhook/Zapier, pipeline dashboard, property-based test suite
    - _Requirements: (delivery)_

- [x] 13. Final checkpoint
  - Ensure all 108 tests pass with `pytest prospect-intelligence/`
  - Confirm no secrets are hard-coded in any source file
  - Confirm `/docs` (Swagger UI) and `/redoc` (ReDoc) render all endpoints defined in Requirements 1–7
  - Ask the user if any questions arise before marking the spec complete.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP iteration
- Each sub-task references specific requirements for traceability
- The project is substantially implemented; these tasks serve as a complete audit checklist
- Property-based testing (Hypothesis) for the Scoring Engine is identified in the design as a 90-day roadmap item and is not included here
- Checkpoints validate incremental correctness; run `pytest --tb=short` after each top-level task group

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["2.1", "2.2"] },
    { "id": 1, "tasks": ["2.3", "2.4", "2.5", "2.6"] },
    { "id": 2, "tasks": ["2.7", "3.1", "6.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "4.1", "6.2"] },
    { "id": 4, "tasks": ["4.2", "4.3", "4.4", "4.5", "5.1", "6.3"] },
    { "id": 5, "tasks": ["4.6", "5.2", "5.3", "5.4", "6.4"] },
    { "id": 6, "tasks": ["5.5", "6.5", "7.1", "8.1"] },
    { "id": 7, "tasks": ["7.2", "7.3", "7.4", "7.5", "8.2", "8.3", "9.1"] },
    { "id": 8, "tasks": ["7.6", "8.4", "8.5", "9.2", "9.3", "9.4"] },
    { "id": 9, "tasks": ["9.5", "10.1", "11.1", "11.2", "11.3", "11.4"] },
    { "id": 10, "tasks": ["10.2", "10.3", "11.5"] },
    { "id": 11, "tasks": ["12.1", "12.2", "12.3", "12.4", "12.5", "12.6"] }
  ]
}
```
