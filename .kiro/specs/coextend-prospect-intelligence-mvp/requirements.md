# Requirements Document

## Introduction

The Coextend Prospect Intelligence MVP is a web application that automates
prospect research for Coextend Global LLP, a façade/construction estimating
and drafting company. Given a prospect's company name, website, and optional
contact details, the system researches the prospect via public web sources,
grounds Coextend's own positioning in a private PDF knowledge base (RAG),
scores the prospect deterministically against a fixed ICP rubric, produces a
founder-ready research brief, exports a CRM-ready record, and optionally
drafts personalised outreach messages — all without inventing facts, executing
automated social-media actions, or writing to a live CRM.

---

## Glossary

- **System**: The Coextend Prospect Intelligence MVP application as a whole.
- **API**: The FastAPI HTTP service layer that exposes all capabilities.
- **Research_Engine**: The component responsible for web search, page fetch,
  and LLM-based structured extraction of prospect facts.
- **Knowledge_Index**: The ChromaDB vector store holding only Coextend's
  internal PDF documents, queried via top-k semantic retrieval with citations.
- **Scoring_Engine**: The deterministic, code-only component that converts
  `ResearchFindings` into a `LeadScore` using the fixed 10-factor rubric.
- **Brief_Generator**: The LLM component that combines `ResearchFindings`,
  `LeadScore`, and retrieved `Knowledge_Index` chunks into a `ResearchBrief`.
- **CRM_Adapter**: The `MockHubSpotAdapter` that maps a `ResearchBrief` to
  HubSpot-style JSON/CSV fields and writes them to `/data/exports/`.
- **Outreach_Generator**: The on-demand LLM component that fills
  message-library templates (retrieved from `Knowledge_Index`) with
  `ResearchFindings` to produce draft messages.
- **Job**: A single asynchronous pipeline execution for one prospect,
  identified by a `job_id` (UUID) and progressing through defined statuses.
- **ResearchFindings**: The structured output of the `Research_Engine`
  containing per-claim evidence labels (Verified / Probable / Unverified)
  and `SourceRef` objects (URL + snippet).
- **LeadScore**: The numeric result (0–100) produced by the `Scoring_Engine`,
  including a per-factor breakdown and rubric version.
- **ResearchBrief**: The final founder-ready document output by the
  `Brief_Generator`, sections matching the Research Output Template.
- **OutreachDrafts**: One draft email and one draft LinkedIn message produced
  by the `Outreach_Generator`, never sent autonomously.
- **SourceRef**: A pairing of a source URL and a short evidence snippet (≤ 300
  characters) that supports a specific claim in `ResearchFindings`.
- **Evidence_Label**: One of three values — Verified, Probable, or Unverified —
  applied to every claim in `ResearchFindings` and `ResearchBrief`.
- **Knowledge_Chunk**: A passage extracted from a Coextend PDF, stored in
  `Knowledge_Index` with `source_document` and `section` metadata.
- **ICP_Rubric**: The fixed 10-factor scoring rubric defined in the Ideal
  Customer Profile PDF, covering trade/service fit, geography, company size,
  tender volume, estimating need, drafting/BIM need, hiring trigger,
  decision-maker access, outsourcing readiness, and commercial attractiveness.
- **Prospect**: A target company under investigation, identified by
  `company_name` and `website`.
- **Founder**: The human operator who reviews briefs, approves outreach, and
  makes final sales decisions.

---

## Requirements

---

### Requirement 1: Prospect Submission and Job Lifecycle

**User Story:** As a Founder, I want to submit a prospect's company name and
website and receive a `job_id` immediately, so that I can track the research
pipeline without waiting for it to complete.

#### Acceptance Criteria

1. WHEN a `POST /api/v1/prospects` request is received with a valid
   `company_name` (non-empty string, maximum 255 characters) and a valid
   `website` (well-formed URL with scheme `http` or `https`, maximum 2048
   characters), THE API SHALL create a `Job` record with `status=pending` and
   return `job_id`, `status`, `created_at`, `company_name`, `website`, and a
   `duplicate_warning` flag within 500 ms.

2. WHEN a `POST /api/v1/prospects` request is received with a missing or empty
   `company_name`, THE API SHALL return HTTP 422 with a structured error body
   identifying the failing field.

3. WHEN a `POST /api/v1/prospects` request is received with a `company_name`
   exceeding 255 characters, THE API SHALL return HTTP 422 with a structured
   error body identifying the failing field.

4. WHEN a `POST /api/v1/prospects` request is received with a `website` value
   that is not a well-formed URL with scheme `http` or `https`, THE API SHALL
   return HTTP 422 with a structured error body identifying the failing field.

5. WHEN a `GET /api/v1/prospects/{job_id}` request is received for an
   existing `job_id`, THE API SHALL return the current `Job` record including
   `status`, `created_at`, `company_name`, `website`, and `duplicate_warning`.

6. WHEN a `GET /api/v1/prospects/{job_id}` request is received for a
   `job_id` that does not exist, THE API SHALL return HTTP 404.

7. THE System SHALL transition each `Job` through the ordered statuses
   `pending → researching → scoring → drafting → complete`, or to
   `failed:<reason>` if any stage raises an unrecoverable error, within 300
   seconds of the `Job` being created.

8. WHEN a `Job` transitions to `failed:<reason>`, THE System SHALL record the
   failure reason string (maximum 1024 characters) in the `Job` record so it
   is visible on the next `GET /api/v1/prospects/{job_id}` call.

9. IF the submitted `website` domain matches the `website` domain of an
   existing `Job` record created within the preceding 24 hours, THEN THE API
   SHALL set `duplicate_warning=true` in the response without rejecting the
   request.

10. THE API SHALL expose a `GET /api/v1/health` endpoint that returns HTTP 200
    and a JSON body `{"status": "ok"}` while the service is running.

---

### Requirement 2: Web-Based Prospect Research

**User Story:** As a Founder, I want the system to research each prospect
using public web sources and extract structured findings, so that I have
evidence-backed information without doing manual searches myself.

#### Acceptance Criteria

1. WHEN a `Job` enters `status=researching`, THE Research_Engine SHALL execute
   at least 3 and at most 10 web search queries targeting the prospect's
   company name, website domain, project/tender activity, decision-makers,
   and growth/hiring signals.

2. WHEN the Research_Engine fetches a web page, THE Research_Engine SHALL
   store the source URL and a short evidence snippet (≤ 300 characters) as a
   `SourceRef` for every material claim (any extracted fact asserted as true
   about the prospect, not hedged as unknown) extracted from that page.

3. WHEN the Research_Engine extracts prospect facts using the LLM, THE
   Research_Engine SHALL assign an Evidence_Label to each claim using these
   rules: `Verified` if the claim is supported by 2 or more `SourceRef`
   objects; `Probable` if supported by exactly 1 `SourceRef`; `Unverified` if
   supported by 0 `SourceRef` objects.

4. WHEN a research section has no supporting evidence from web sources, THE
   Research_Engine SHALL record a `notes_missing` entry for that section
   rather than omitting it silently or fabricating content.

5. IF a web search call returns a non-2xx HTTP status or times out after 10
   seconds, THEN THE Research_Engine SHALL retry up to 3 times with
   exponential backoff (base 1.5 s) before marking that search attempt as
   failed and continuing with available results.

6. IF a page-fetch call returns a non-2xx HTTP status or times out after 15
   seconds, THEN THE Research_Engine SHALL retry up to 3 times with
   exponential backoff (base 1.5 s) before skipping that URL and logging the
   failure.

7. WHEN the Research_Engine completes extraction, THE Research_Engine SHALL
   produce a `ResearchFindings` object containing: `company_name`, `website`,
   `snapshot`, `contacts`, `projects_signals`, `likely_requirements`,
   `pain_hypotheses`, `risks_unknowns`, `sources` (list of `SourceRef`), and
   `notes_missing` (list of section names lacking evidence).

8. THE Research_Engine SHALL never include Coextend-internal facts (from the
   `Knowledge_Index`) in the `ResearchFindings` object; prospect findings and
   internal knowledge MUST remain in separate data structures.

9. IF every web search query attempt fails (all queries exhausted or all
   return errors), THEN THE Research_Engine SHALL transition the `Job` to
   `failed:insufficient_web_data` rather than producing an empty
   `ResearchFindings` object.

10. IF the Research_Engine fails to start due to a system-level error (e.g.,
    process crash, dependency unavailable), THEN THE System SHALL retain the
    `Job` in `status=researching` and retry Research_Engine startup up to 2
    times before transitioning the `Job` to
    `failed:research_engine_unavailable`.

---

### Requirement 3: Internal Knowledge Retrieval (RAG Layer)

**User Story:** As a Founder, I want the system to ground its understanding
of Coextend's services, ICP, and messaging in our own PDF documents (with
citations), so that the brief accurately reflects our positioning rather than
generic or invented content.

#### Acceptance Criteria

1. WHEN a `POST /api/v1/knowledge/ingest` request is received, THE
   Knowledge_Index SHALL process every PDF file present in `/data/knowledge_base/`,
   extract text using a heading-aware chunking strategy that preserves
   `source_document` and `section` metadata per chunk, embed each chunk using
   the configured embedding model, and store all chunks in the
   `coextend_knowledge` ChromaDB collection.

2. WHEN the `Brief_Generator` or `Outreach_Generator` queries the
   Knowledge_Index with a semantic search phrase, THE Knowledge_Index SHALL
   return the top-k (configurable, default 5) matching `Knowledge_Chunk`
   objects, each carrying `source_document`, `section`, `text`, and
   `relevance_score` (a float in the range [0.0, 1.0]).

3. THE Knowledge_Index SHALL only ever contain chunks from Coextend's own
   PDF documents; IF prospect-specific `ResearchFindings` or other
   non-Coextend content is inadvertently written to the `coextend_knowledge`
   collection, THE Knowledge_Index SHALL detect and remove such entries during
   the next ingest operation rather than rejecting the triggering write at
   insertion time.

4. WHEN the `Brief_Generator` includes a `Knowledge_Chunk` in a prompt, THE
   Brief_Generator SHALL label the chunk's origin as `[Internal: <source_document>]`
   in the prompt so the LLM can distinguish it from prospect findings.

5. WHEN the `Brief_Generator` produces a `ResearchBrief`, THE Brief_Generator
   SHALL include a `knowledge_citations` list that maps each statement
   directly derived from a `Knowledge_Chunk` included in the prompt to its
   `source_document` and `section`.

6. IF the Knowledge_Index contains no chunks for a given query (empty
   retrieval result), THEN THE Brief_Generator SHALL populate the affected
   `ResearchBrief` section with the explicit statement
   `"No relevant internal knowledge available"` rather than proceeding
   without attribution.

7. THE Knowledge_Index SHALL support re-ingestion atomically: WHEN
   `/api/v1/knowledge/ingest` is called again, THE Knowledge_Index SHALL
   replace the existing `coextend_knowledge` collection contents with the
   newly processed chunks in a single atomic operation; IF the replacement
   fails mid-way, THE Knowledge_Index SHALL retain the previous collection
   contents unchanged.

8. IF a PDF file present in `/data/knowledge_base/` is corrupt or
   unreadable during ingest, THEN THE Knowledge_Index SHALL skip that file,
   log the filename and error reason, and continue processing remaining files
   without transitioning the ingest request to a failure state.

9. IF the `/data/knowledge_base/` directory is empty or contains no PDF
   files, THEN THE Knowledge_Index SHALL return HTTP 200 with a response body
   indicating zero chunks were ingested rather than returning an error.

---

### Requirement 4: Deterministic Lead Scoring

**User Story:** As a Founder, I want each prospect scored out of 100 using
our fixed ICP rubric — in code, not by the LLM — so that the same research
data always produces the same score and I can trust the ranking.

#### Acceptance Criteria

1. THE Scoring_Engine SHALL evaluate `ResearchFindings` against the ICP_Rubric
   and compute a `LeadScore` composed of 10 named factors: `trade_service_fit`,
   `geography`, `company_size`, `tender_volume`, `estimating_need`,
   `drafting_bim_need`, `hiring_trigger`, `decision_maker_access`,
   `outsourcing_readiness`, and `commercial_attractiveness`.

2. THE Scoring_Engine SHALL assign each factor a numeric score within the
   point range defined in the ICP_Rubric and sum all 10 factor scores to
   produce a total score in the range [0, 100]; the `LeadScore` SHALL also
   include a `band` field set to `Hot` (total ≥ 70), `Warm` (total ≥ 40),
   `Cool` (total ≥ 20), or `Cold` (total < 20).

3. THE Scoring_Engine SHALL be implemented as a pure function: given identical
   `ResearchFindings` input within the same execution session, THE
   Scoring_Engine SHALL always return an identical `LeadScore` output with no
   randomness, LLM calls, or external I/O; minor environment-specific
   variations such as floating-point precision differences across different
   hardware or Python runtime versions are acceptable across sessions.

4. THE Scoring_Engine SHALL record a `rubric_version` string in the
   `LeadScore` output so that scores can be compared across rubric revisions.

5. WHEN a scoring factor's associated finding fields are absent from all lists
   in `ResearchFindings`, THE Scoring_Engine SHALL assign that factor a score
   of 0 and record the factor name in `LeadScore.zero_evidence_factors`.

6. THE Scoring_Engine SHALL expose its scoring logic through individually
   testable functions — one per ICP rubric factor — so that each factor can be
   unit-tested independently with known input/output pairs, including the
   0-points / no-evidence path.

7. WHEN the `Scoring_Engine` receives `ResearchFindings` where all finding
   lists are empty, THE Scoring_Engine SHALL return a `LeadScore` with a
   total score of 0 and all 10 factors listed in `zero_evidence_factors`.

---

### Requirement 5: Founder-Ready Research Brief

**User Story:** As a Founder, I want a concise research brief for each
prospect that follows our standard template, labels every claim, and never
invents missing information, so that I can review and act on it confidently.

#### Acceptance Criteria

1. WHEN a `Job` enters `status=drafting`, THE Brief_Generator SHALL produce a
   `ResearchBrief` containing all 11 sections of the Research Output Template:
   `snapshot`, `contact`, `company_research`, `projects_signals`,
   `likely_requirements`, `pain_hypotheses`, `lead_score`, `recommended_approach`,
   `risks_unknowns`, `next_action`, and `sources`; IF any section is absent
   from the output, THEN THE Brief_Generator SHALL transition the `Job` to
   `failed:incomplete_brief`.

2. THE Brief_Generator SHALL assign an Evidence_Label of exactly one of the
   values `Verified`, `Probable`, or `Unverified` to every factual claim in
   the `ResearchBrief`; IF the post-generation validation function detects any
   claim without an Evidence_Label, THEN THE Brief_Generator SHALL reject the
   brief and transition the `Job` to `failed:missing_label`.

3. IF a `ResearchBrief` section has no evidence from `ResearchFindings` or
   `Knowledge_Index` retrieval, THEN THE Brief_Generator SHALL populate that
   section with the explicit statement `"No evidence available"` and assign
   the Evidence_Label `Unverified` to that section, rather than omitting the
   section or generating speculative content.

4. THE Brief_Generator SHALL include a `sources` section listing every
   `SourceRef` URL and evidence snippet that supports a claim in the brief;
   IF a claim is labeled `Verified` or `Probable` but has no corresponding
   `SourceRef` entry in the `sources` section, THEN THE Brief_Generator SHALL
   downgrade that claim's Evidence_Label to `Unverified`.

5. THE Brief_Generator SHALL include the `LeadScore` total and per-factor
   breakdown in the `lead_score` section of the `ResearchBrief`; the
   `LeadScore` total SHALL be a numeric value in the range 0 to 100 inclusive,
   and each per-factor score SHALL be a non-negative numeric value whose sum
   equals the total.

6. WHEN the `ResearchBrief` is retrieved via `GET /api/v1/prospects/{job_id}/brief`,
   THE API SHALL return the brief as JSON by default and as Markdown when the
   query parameter `?format=markdown` is supplied; IF no `ResearchBrief`
   exists for the given `job_id`, THEN THE API SHALL return HTTP 404.

7. THE Brief_Generator SHALL constrain LLM output using a structured JSON
   schema so that the output matches the `ResearchBrief` data model; IF the
   LLM returns malformed JSON, THEN THE Brief_Generator SHALL re-prompt once
   using the same input within 30 seconds; IF the second attempt also returns
   malformed JSON, THEN THE Brief_Generator SHALL transition the `Job` to
   `failed:llm_parse_error`.

8. THE Brief_Generator SHALL never upgrade an Evidence_Label from a lower
   confidence to a higher confidence (e.g., `Unverified` to `Probable`,
   `Unverified` to `Verified`, or `Probable` to `Verified`) at output time;
   a post-generation validation function SHALL compare each output
   Evidence_Label against the highest confidence level supported by the source
   evidence and reject the entire brief if any label exceeds its evidential
   basis, transitioning the `Job` to `failed:label_escalation`.

9. IF the `ResearchBrief` generation step exceeds 120 seconds from the moment
   the `Job` enters `status=drafting`, THEN THE Brief_Generator SHALL abort
   generation and transition the `Job` to `failed:brief_timeout`, preserving
   any partial findings already written to `ResearchFindings`.

---

### Requirement 6: CRM Export

**User Story:** As a Founder, I want each completed brief exported as a
HubSpot-style JSON and CSV record, so that I can import prospects into a CRM
without manual re-entry, with no risk of writing to the live CRM during the
MVP phase.

#### Acceptance Criteria

1. WHEN a `Job` reaches `status=complete`, THE CRM_Adapter SHALL automatically
   map the `ResearchBrief` to a HubSpot-compatible record containing at
   minimum: `company_name`, `website`, `lead_score`, `lead_band`
   (Hot / Warm / Cool / Cold), `contact_name`, `contact_title`,
   `recommended_approach` (≤ 280 characters), `next_action` (≤ 280 characters),
   and `sources_summary` (≤ 500 characters, URL list format).

2. WHEN a `Job` reaches `status=complete`, THE CRM_Adapter SHALL write the
   mapped record as both a `.json` file and a `.csv` file to `/data/exports/`
   using the filename pattern `{job_id}_{company_name_slug}.{ext}`, where
   `company_name_slug` is formed by lowercasing the name, replacing any
   non-alphanumeric character with a hyphen, collapsing consecutive hyphens
   into one, and truncating at 60 characters; IF a file with the same name
   already exists, THE CRM_Adapter SHALL overwrite it.

3. WHEN a new `Job` is submitted, THE CRM_Adapter SHALL check whether
   `company_name` (normalised: lowercased, leading/trailing whitespace stripped,
   internal whitespace collapsed to a single space) matches any record in the
   sample CRM dataset at `/data/crm_sample/sample_crm.json` and set
   `duplicate_warning=true` in the `Job` response if a match is found.

4. IF the `/data/crm_sample/sample_crm.json` file is absent or unparseable,
   THEN THE CRM_Adapter SHALL set `duplicate_warning=false` and include a
   `duplicate_check_warning` field in the `Job` response noting that the
   sample CRM dataset could not be loaded.

5. WHEN a `GET /api/v1/prospects/{job_id}/crm-export` request is received,
   THE CRM_Adapter SHALL return the JSON export by default and the CSV export
   when the query parameter `?format=csv` is supplied.

6. IF no export file exists for the requested `job_id` and format, THEN THE
   API SHALL return HTTP 404 with a structured error body.

7. THE CRM_Adapter SHALL implement a `CRMAdapterInterface` that isolates all
   HubSpot field mappings behind a defined contract, so that a live
   `HubSpotAdapter` can be substituted for the `MockHubSpotAdapter` without
   changes to the calling code.

8. THE CRM_Adapter SHALL never make outbound HTTP calls to any CRM API;
   all writes in the MVP SHALL be to the local filesystem only.

---

### Requirement 7: Outreach Draft Generation

**User Story:** As a Founder, I want the system to draft a personalised
outreach email and LinkedIn message using our own message templates, so that
I have a strong starting point without doing it manually — with the
understanding that I review and send these myself.

#### Acceptance Criteria

1. WHEN a `POST /api/v1/prospects/{job_id}/outreach` request is received for a
   `Job` with `status=complete`, THE Outreach_Generator SHALL retrieve
   message-library `Knowledge_Chunk` objects from the `Knowledge_Index` and
   produce an `OutreachDrafts` object containing one draft email (body ≤ 300
   words) and one draft LinkedIn message (body ≤ 300 characters).

2. WHEN a `POST /api/v1/prospects/{job_id}/outreach` request is received for a
   `Job` whose `status` is not `complete`, THE API SHALL return HTTP 409 with
   a structured error body stating that outreach generation requires a
   completed research job.

3. IF `ResearchFindings` contains at least one claim with Evidence_Label
   `Verified` or `Probable`, THEN THE Outreach_Generator SHALL personalise
   each draft by substituting prospect-specific values derived from those
   claims into message-library template placeholders; it SHALL NOT state any
   `Unverified` finding as a confirmed fact in a draft message.

4. THE Outreach_Generator SHALL include a `draft_status` field on each message
   in `OutreachDrafts` set to `draft`, clearly indicating that the message has
   not been sent and requires human review before use.

5. THE System SHALL never send, schedule, or submit any outreach message to
   any external platform autonomously; all sending actions SHALL remain
   human-controlled.

6. THE System SHALL never perform automated LinkedIn connection requests,
   automated LinkedIn messaging, or LinkedIn profile scraping at scale.

7. WHEN the `Outreach_Generator` cannot find any matching message-library
   templates in the `Knowledge_Index`, THE Outreach_Generator SHALL return an
   `OutreachDrafts` object with both message body fields set to an empty
   string and a `notes` field explaining that no templates were available.

8. WHEN a `POST /api/v1/prospects/{job_id}/outreach` request is received for a
   `job_id` that does not exist, THE API SHALL return HTTP 404 with a
   structured error body.

9. IF `ResearchFindings` contains no claims with Evidence_Label `Verified` or
   `Probable`, THEN THE Outreach_Generator SHALL return an `OutreachDrafts`
   object with both message body fields set to an empty string and a `notes`
   field explaining that no verified or probable claims were available for
   personalisation; THE Outreach_Generator SHALL still set `draft_status` to
   `draft` on both message objects in the returned `OutreachDrafts`.

---

### Requirement 8: Web UI and API Surface

**User Story:** As a Founder, I want a minimal web interface to submit
prospects and view results, backed by a documented REST API, so that I can
use the system from a browser and integrate it with other tools later.

#### Acceptance Criteria

1. THE System SHALL provide a web UI accessible at the root path (`/`) that
   presents a form requiring `company_name` and `website`, and accepting
   optional `known_contact_name` and `known_contact_title`; IF the form is
   submitted with `company_name` or `website` empty, THE UI SHALL display an
   inline validation error and SHALL NOT submit the request.

2. WHEN the web UI form is submitted, THE System SHALL display the `job_id`
   and current `status`, and SHALL poll `GET /api/v1/prospects/{job_id}` at a
   configurable interval (default 5 seconds, minimum 3 seconds, maximum 30
   seconds) for up to 300 seconds; IF `status` remains neither `complete` nor
   `failed:<reason>` after 300 seconds, THE UI SHALL display a timeout error
   and stop polling.

3. WHEN a `Job` reaches `status=complete`, THE System SHALL display in the web
   UI, without requiring the Founder to call the API directly: company name,
   lead score and band, up to 3 top pain-point hypotheses, and the recommended
   outreach action; THE System SHALL update the web UI display on the next
   poll cycle without introducing additional delay beyond the configured poll
   interval.

4. THE API SHALL expose interactive documentation at `/docs` (Swagger UI) and
   `/redoc` (ReDoc) that covers all endpoints defined in Requirements 1–7.

5. THE System SHALL validate all API request bodies using Pydantic v2 models
   and return HTTP 422 with a structured validation error body (including
   `loc`, `msg`, and `type` fields per Pydantic v2 error schema) for any
   request that fails validation.

6. THE System SHALL write structured JSON log entries for every API request,
   `Job` status transition, external call attempt, retry, and failure,
   including `job_id`, `timestamp`, `level`, and `message` fields.

7. THE System SHALL load all secrets (API keys, database path, ChromaDB path)
   from environment variables or a `.env` file; no secret value SHALL be
   hard-coded in source files.

---

### Requirement 9: Reliability, Retries, and Graceful Failure

**User Story:** As a Founder, I want the system to handle transient failures
(bad URLs, timeouts, malformed LLM output) gracefully and without crashing,
so that a single bad prospect or network blip does not disrupt the whole
pipeline.

#### Acceptance Criteria

1. WHEN any external HTTP call (web search, page fetch, LLM API) fails with a
   transient error (5xx status, connection timeout, rate-limit 429), THE
   System SHALL retry up to 3 times with exponential backoff starting at a
   1.5-second base delay, doubling on each attempt, capped at a maximum delay
   of 30 seconds, before treating the call as failed.

2. IF all retry attempts for a critical pipeline step (research extraction,
   brief generation) are exhausted, THEN THE System SHALL transition the
   `Job` to `failed:<reason>` within 5 seconds of the final retry attempt,
   record a reason string of at most 500 characters, and cease all further
   processing for that `Job`.

3. IF a non-critical pipeline step (a single web-search query or a single
   page fetch) exhausts its retries, THEN THE System SHALL log the failure
   with the step identifier and failure reason, continue processing with the
   remaining available results, and append an entry of at most 500 characters
   describing the missed step to `ResearchFindings.notes_missing`.

4. WHEN the LLM returns a JSON response that does not conform to the expected
   schema, THE System SHALL re-prompt the LLM once, including the original
   schema definition and the specific validation error message, within 10
   seconds of detecting the non-conformance.

5. IF the second LLM response also does not conform to the expected schema,
   THEN THE System SHALL transition the `Job` to `failed:llm_parse_error`
   and cease all further processing for that `Job`.

6. WHEN a `POST /api/v1/prospects` request is received with a `website` value
   that is syntactically valid but unreachable (DNS failure, connection
   refused) after all retry attempts are exhausted, THE Research_Engine SHALL
   append an entry of at most 500 characters describing the fetch failure to
   `ResearchFindings.notes_missing` and continue processing using
   search-engine results only.

7. THE System SHALL return a structured error response body containing an
   `error_code` field (a non-empty string) and a `message` field (a
   human-readable string of at most 500 characters) for all HTTP 4xx and 5xx
   responses; unhandled exceptions SHALL never be surfaced as bare stack
   traces to API clients.

---

### Requirement 10: Anti-Fabrication and Evidence Integrity

**User Story:** As a Founder, I want a guarantee that the system never invents
facts, names, projects, or contact details, so that I can trust the brief
enough to use it in real sales conversations.

#### Acceptance Criteria

1. THE Brief_Generator SHALL be prompted with an explicit instruction
   prohibiting the invention of company names, project names, contact details,
   revenue figures, or any factual claim not present in `ResearchFindings` or
   retrieved `Knowledge_Chunk` objects.

2. WHEN `ResearchFindings` lacks evidence for a specific section, THE
   Brief_Generator SHALL populate that section with the explicit marker string
   `"[EVIDENCE MISSING]"` followed by the section name; it SHALL NOT generate
   any content for that section beyond this marker.

3. THE System SHALL include an automated post-generation check that verifies
   no Evidence_Label in the `ResearchBrief` was upgraded to a higher
   confidence level relative to the corresponding label in `ResearchFindings`
   (where `Verified` > `Probable` > `Unverified`); IF an upgrade is detected
   THEN THE System SHALL reject the brief and transition the `Job` to
   `failed:label_upgrade_violation`; the post-generation check MAY also
   transition the `Job` to a failed state for other quality violations beyond
   label upgrades, using an appropriate `failed:<reason>` code.

4. WHEN the Brief_Generator is invoked with `ResearchFindings` in which all
   prospect-specific finding lists are empty, THE System SHALL produce a
   `ResearchBrief` in which every factual section contains the marker string
   `"[EVIDENCE MISSING]"` and no section contains any generated factual claim.

5. WHEN the Outreach_Generator is invoked and `ResearchFindings` contains one
   or more claims labeled `Unverified`, THE Outreach_Generator SHALL produce
   `OutreachDrafts` in which no `Unverified` claim text appears verbatim as a
   stated fact.

6. THE Research_Engine SHALL store a `SourceRef` (URL + snippet) for every
   Verified or Probable claim; IF a Verified or Probable claim has no
   associated `SourceRef`, THEN THE System SHALL downgrade the Evidence_Label
   to Unverified automatically before producing `ResearchFindings`.

7. IF the automated post-generation check (Requirement 10.3) fails to execute
   due to a system error, THEN THE Brief_Generator SHALL log the check failure
   and MAY still deliver the `ResearchBrief` to the `Job` record, but SHALL
   set a `validation_skipped=true` flag on the `ResearchBrief` to indicate
   the check did not run.
