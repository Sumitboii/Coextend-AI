# Implementation Plan — Coextend Prospect Intelligence MVP

# Implementation Plan — Coextend Prospect Intelligence MVP

- [x] 1. Project scaffolding and architecture note
  - Initialize repository structure (`/api`, `/engine`, `/knowledge`,
    `/scoring`, `/tests`, `/data/knowledge_base`, `/data/exports`)
  - Set up FastAPI app skeleton with `/health` endpoint
  - Write a one-page architecture note summarizing the design (components, data
    flow, risks, test plan) as `docs/architecture.md`
  - Add `.env.example` with placeholders for LLM API key, search API key — no
    real secrets committed
  - _Requirements: 9.1, 10.3_

- [x] 2. Core data models
  - [x] 2.1 Implement Pydantic models: `ProspectRequest`, `SourceRef`,
    `EvidenceLabel`, `Finding`, `ResearchFindings`, `ScoreFactor`, `LeadScore`,
    `ResearchBrief`, `OutreachDrafts`, `CRMExportRecord`
  - [x] 2.2 Write schema validation unit tests (required fields, URL validation,
    enum constraints)
  - _Requirements: 1.2, 3.6, 4.1, 5.1, 6.1, 7.5_

- [x] 3. Job intake and lifecycle
  - [x] 3.1 Implement `POST /prospects`: validate input, create job record with
    status `pending`, return `job_id` immediately
  - [x] 3.2 Implement duplicate-submission cooldown check
  - [x] 3.3 Implement `GET /prospects/{job_id}` returning current status
  - [x] 3.4 Add job status state machine (`pending -> researching -> scoring ->
    drafting -> complete` / `failed:<reason>`)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.3, 9.4_

- [x] 4. Knowledge ingestion (internal RAG layer)
  - [x] 4.1 Build PDF text extraction + heading-aware chunking pipeline for the
    Coextend knowledge PDFs
  - [x] 4.2 Implement embedding + vector store indexing with
    `{source_document, section, page}` metadata per chunk
  - [x] 4.3 Implement `POST /knowledge/ingest` for re-ingestion on document
    update, no code change required
  - [x] 4.4 Implement retrieval function returning top-k chunks with citations,
    scoped strictly to internal knowledge (never prospect findings)
  - [x] 4.5 Write a grounding/citation test: ask a known internal-knowledge
    question and assert the answer traces to the correct source document
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_

- [x] 5. External research engine
  - [x] 5.1 Implement web search + page fetch/extract utilities with timeout and
    retry/backoff
  - [x] 5.2 Implement structured extraction (LLM, JSON-schema constrained) of
    company snapshot, decision-makers, and projects/signals into `Finding`
    objects, each carrying `SourceRef`s
  - [x] 5.3 Ensure any section with no reliable evidence is recorded explicitly
    in `notes_missing` rather than omitted or guessed
  - [x] 5.4 Write tests on 3+ sample prospects verifying findings carry source
    URLs and evidence labels
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 6. Deterministic lead scoring engine
  - [x] 6.1 Implement the ten-factor scoring config module (weights + banded
    point rules) with an explicit `rubric_version` string
  - [x] 6.2 Implement `score(findings) -> LeadScore` as a pure function reading
    only `ResearchFindings` fields — no LLM call inside this function
  - [x] 6.3 Implement priority-band assignment from fixed score thresholds
  - [x] 6.4 Unit test each factor's scoring rule independently (including the
    "0 points / no evidence" path)
  - [x] 6.5 Write a score-repeatability test: same `ResearchFindings` scored
    twice yields an identical `LeadScore`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 7. Research brief generator
  - [x] 7.1 Implement JSON-schema-constrained LLM call that assembles a
    `ResearchBrief` from `ResearchFindings` + `LeadScore` + retrieved internal
    knowledge chunks
  - [x] 7.2 Enforce prompt-level separation: prospect facts only from findings,
    Coextend facts only from retrieval, with citations attached
  - [x] 7.3 Enforce evidence-label pass-through (no silent upgrade to Verified)
  - [x] 7.4 Implement `GET /prospects/{job_id}/brief` (JSON) plus a
    human-readable render (e.g., Markdown/HTML) for the UI
  - [x] 7.5 Write the "refuses to invent missing information" test case
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 8.1, 8.2, 8.3, 8.4_

- [x] 8. CRM export adapter
  - [x] 8.1 Define `CRMAdapter` interface (`export(brief) -> CRMExportRecord`)
  - [x] 8.2 Implement `MockHubSpotAdapter` writing JSON + CSV to
    `/data/exports/`, mapped to HubSpot-style company/contact/deal fields
  - [x] 8.3 Implement duplicate detection against a provided sample CRM dataset,
    setting `possible_duplicate`
  - [x] 8.4 Implement `GET /prospects/{job_id}/crm-export`
  - [x] 8.5 Write a duplicate-detection test
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 8.5_

- [x] 9. Outreach draft generator
  - [x] 9.1 Implement JSON-schema-constrained LLM call that fills the approved
    email/LinkedIn template structure from `ResearchBrief` Verified/Probable
    findings and retrieved message-library templates
  - [x] 9.2 Mark all output `status: "draft"`; confirm no send/schedule
    capability exists anywhere in this code path
  - [x] 9.3 Implement `POST /prospects/{job_id}/outreach`
  - [x] 9.4 Write a test asserting drafts never state an Unverified finding as
    fact
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 10. Minimal UI
  - [x] 10.1 Build a simple form (company name, website, optional contact) that
    calls `POST /prospects`
  - [x] 10.2 Build a status/results view polling job status and rendering the
    brief, CRM export download, and outreach drafts once complete
  - [x] 10.3 Surface `failed:<reason>` errors in plain language in the UI
  - _Requirements: 9.2, 9.3_

- [x] 11. Logging, reliability, and end-to-end evaluation
  - [x] 11.1 Add structured logging for each pipeline step (no secrets logged)
  - [x] 11.2 Add retry/backoff wrapper applied to all external calls
    (search, fetch, LLM, retrieval)
  - [x] 11.3 Add one automatic re-prompt on malformed LLM JSON before failing
    the job
  - [x] 11.4 Implement the failure-injection test (bad URL / timeout / missing
    field / malformed output) and assert graceful failure
  - [x] 11.5 Run the full test suite across 5 prospects (1 poor-fit, 2
    ambiguous) and record results
  - _Requirements: 10.1, 10.2, 10.4, 10.5, 10.6_

- [x] 12. Documentation and delivery package
  - [x] 12.1 Write README: installation, configuration, architecture summary,
    run instructions
  - [x] 12.2 Export the architecture diagram (from `docs/architecture.md` /
    design.md Mermaid diagram) as an image
  - [x] 12.3 Provide `.env.example` (secrets omitted) and sample input/output
    files for at least 2 test prospects
  - [x] 12.4 Document known limitations and technical debt
  - [x] 12.5 Write the monthly cost estimate at 100 / 500 / 2,000
    prospects/month with stated assumptions
  - [x] 12.6 Write the 30/60/90-day roadmap
  - _Requirements: (supports overall delivery — see design.md "Cost
    Estimation" and "Roadmap Placeholder")_

