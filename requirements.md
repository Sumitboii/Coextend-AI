# Requirements Document — Coextend Prospect Intelligence MVP

## Introduction

Coextend Global LLP's founder currently spends significant time manually
researching prospective façade/construction clients, judging fit, and drafting
outreach. This MVP is an AI-assisted prospect intelligence system that, given a
company name and website, researches the prospect, grounds its understanding of
Coextend's own services/positioning in a PDF knowledge base, scores the prospect
deterministically against the approved 100-point rubric, and produces a
founder-ready brief, a CRM-ready record, and optional outreach drafts — all
without inventing facts and without taking any automated outbound action.

The system has two knowledge sources that must remain architecturally separate:
1. **External research** — live, per-prospect findings from the public web.
2. **Internal knowledge** — Coextend's own PDFs (agent instructions, company
   profile, services, capabilities, ICP, sales positioning, research criteria,
   research output template, marketing strategy, message libraries, proposal
   templates), ingested once and retrieved (RAG) with citations.

## Requirements

### Requirement 1 — Prospect Intake

**User Story:** As a salesperson, I want to submit a prospect by company name and
website (and optionally a known contact), so that I can trigger automated
research without manual data entry.

#### Acceptance Criteria
1. WHEN a user submits a company name and website through the UI or API THEN the
   system SHALL create a new research job with a unique job ID and a `pending`
   status.
2. IF the website URL is missing or fails basic URL validation THEN the system
   SHALL reject the request with a specific validation error and SHALL NOT create
   a job.
3. IF an optional contact name and/or title is supplied THEN the system SHALL
   store it as a "known contact to verify" rather than treat it as a system
   finding.
4. WHEN a job is created THEN the system SHALL return the job ID immediately so
   the client can poll or subscribe for status without blocking on research
   completion.
5. WHEN the same company name + website is submitted again within a configurable
   cooldown window THEN the system SHALL warn the user of the likely duplicate
   before creating a new job.

### Requirement 2 — External Company & Contact Research

**User Story:** As a salesperson, I want the system to research a prospect's
public company information, decision-makers, and recent projects/signals, so
that I have decision-ready context without doing the research myself.

#### Acceptance Criteria
1. WHEN a research job runs THEN the system SHALL gather, at minimum, company
   overview, location, services/sectors, approximate size, and operating regions
   from the company website and other public sources.
2. WHEN a research job runs THEN the system SHALL attempt to identify relevant
   decision-makers from the target title list (e.g., Managing Director,
   Commercial Director, Pre-Construction Director, Estimating Director/Manager,
   Technical Director, Design Manager, Procurement/QS leadership) and SHALL
   record why each identified person is relevant.
3. WHEN a research job runs THEN the system SHALL search for recent/current
   projects, tenders, frameworks, awards, appointments, hiring activity, and
   other buying signals, and SHALL record a publication date for each when
   available.
4. WHEN the system records a material claim about the prospect THEN it SHALL
   store the supporting source URL alongside the claim.
5. IF a material claim can only be supported by a single low-quality source and a
   better source exists THEN the system SHALL prefer the better source.
6. IF no reliable evidence is found for a given research section THEN the system
   SHALL explicitly record "no evidence found" for that section rather than
   omitting it silently or guessing.

### Requirement 3 — Internal Knowledge Grounding (RAG over Coextend PDFs)

**User Story:** As the founder, I want the system's understanding of Coextend's
own services, ICP, and positioning to come from our approved internal documents,
so that generated briefs and outreach stay consistent with our actual offering
and do not drift or hallucinate capabilities we don't have.

#### Acceptance Criteria
1. WHEN the system is deployed THEN it SHALL ingest the supplied Coextend
   knowledge PDFs into a retrieval index (embeddings + vector store), keeping
   each chunk traceable to its source document and section.
2. WHEN the system needs internal knowledge (service descriptions, ICP criteria,
   scoring rubric, positioning language, message templates, standards
   references) THEN it SHALL retrieve relevant chunks from the index rather than
   relying on a single large system prompt containing the entire knowledge base.
3. WHEN the system generates any output that references Coextend's services,
   capabilities, or positioning THEN it SHALL cite the source document (e.g.,
   "03 - Company Capabilities") that grounds that statement.
4. IF a knowledge PDF is updated or replaced THEN the system SHALL support
   re-ingestion without requiring a code change.
5. WHEN the system cannot find relevant internal knowledge for a claim it is
   about to make about Coextend THEN it SHALL omit the claim rather than
   generate it ungrounded.
6. WHEN retrieval is tested THEN at least one automated test SHALL prove that a
   specific internal-knowledge answer is traceable to a specific ingested
   document (a grounding/citation test).

### Requirement 4 — Deterministic Lead Scoring

**User Story:** As the founder, I want every prospect scored out of 100 points
using our approved rubric, so that scores are consistent, explainable, and not
subject to the AI's mood or phrasing on a given day.

#### Acceptance Criteria
1. WHEN a research job completes its findings THEN the system SHALL compute a
   0–100 lead score using deterministic, code-based logic (not an LLM free-text
   guess) against the ten weighted factors defined in the Ideal Customer Profile
   document (trade/service fit 20, geography 10, company size/capacity need 10,
   tender/project volume 15, estimating/take-off need 10, drafting/BIM need 10,
   hiring/capacity trigger 10, decision-maker access 5, outsourcing readiness 5,
   commercial attractiveness 5).
2. WHEN the score is computed THEN the system SHALL return a per-factor
   breakdown (factor, weight, points awarded, and the evidence used to award
   those points) alongside the total.
3. WHEN the score is computed THEN the system SHALL assign a priority band
   (e.g., High / Medium / Low) using fixed, documented thresholds.
4. WHEN the same underlying research findings are scored twice THEN the system
   SHALL return the identical total score and breakdown both times (score
   repeatability).
5. IF evidence for a factor is missing or ambiguous THEN the system SHALL award
   the documented "0 / no evidence" points for that factor rather than
   estimating or rounding up.
6. WHEN scoring logic changes THEN the system SHALL version the rubric so past
   scores remain attributable to the rubric version that produced them.

### Requirement 5 — Research Brief Generation

**User Story:** As a salesperson, I want a concise, founder-ready research brief
for each prospect, so that I can review it in 3–5 minutes before outreach or a
meeting.

#### Acceptance Criteria
1. WHEN a research job completes THEN the system SHALL generate a brief
   containing all sections of the existing Research Output Template: prospect
   snapshot, contact/decision-maker, company research, projects and buying
   signals, likely requirements, pain-point hypotheses, lead score, recommended
   approach, risks/unknowns, next action, and sources.
2. WHEN the brief states a fact about the prospect THEN the system SHALL label it
   Verified, Probable, or Unverified per the approved evidence-label definitions.
3. WHEN the brief presents a pain-point hypothesis or a likely requirement THEN
   the system SHALL present it explicitly as a hypothesis, never as a confirmed
   fact.
4. IF information required for a section is unavailable THEN the system SHALL
   state what is missing in that section rather than fabricating a plausible
   answer.
5. WHEN the brief is generated THEN the system SHALL list every source URL used,
   with the date it was reviewed where available.
6. WHEN the brief is generated THEN the system SHALL be renderable both as
   structured data (for the API) and as a human-readable document (for the UI).

### Requirement 6 — CRM-Ready Export

**User Story:** As the founder, I want each completed research job exported as a
CRM-ready record, so that qualified leads can be loaded into our CRM without
manual re-entry.

#### Acceptance Criteria
1. WHEN a research job completes THEN the system SHALL produce a JSON record and
   a CSV row mapped to HubSpot-style contact/company/deal fields.
2. WHEN the export is produced THEN the system SHALL write it to a mock/sandbox
   destination only; the system SHALL NOT perform any live write to a production
   CRM in this MVP.
3. WHEN the export includes the lead score THEN it SHALL include both the total
   score and the priority band.
4. IF a company or contact already appears to exist in the (mocked) CRM records
   provided for testing THEN the system SHALL flag the likely duplicate rather
   than silently creating a second record.
5. WHEN the export adapter is implemented THEN it SHALL expose a clearly defined
   interface so a real HubSpot integration can be substituted later without
   changing the rest of the system.

### Requirement 7 — Outreach Draft Generation

**User Story:** As a salesperson, I want an optional draft email and LinkedIn
message generated from the research and our approved message library, so that I
can review and personalize before sending, without the system contacting the
prospect itself.

#### Acceptance Criteria
1. WHEN a user requests outreach drafts for a completed research job THEN the
   system SHALL generate one email draft and one LinkedIn message draft, based on
   the templates and structure ("observation → likely problem → relevant
   capability → low-friction next step") in the message-library PDFs.
2. WHEN a draft references a specific observation about the prospect THEN it
   SHALL use only Verified or Probable findings from that job's research, not
   Unverified hypotheses stated as fact.
3. THE system SHALL NOT send, schedule, or otherwise transmit any message to the
   prospect; drafts are output only.
4. THE system SHALL NOT perform any automated LinkedIn action (connection
   request, message send, or bulk profile scraping).
5. WHEN a draft is generated THEN the system SHALL mark it clearly as
   "draft — requires human review before use."

### Requirement 8 — Anti-Fabrication and Evidence Discipline

**User Story:** As the founder, I want a hard guarantee that the system never
invents prospect facts, so that I can trust and act on its output without
independently re-verifying everything.

#### Acceptance Criteria
1. THE system SHALL NOT generate a company name, person name, project name, or
   contact detail that is not backed by a retrieved source.
2. WHEN the system is uncertain whether a retrieved detail is accurate THEN it
   SHALL label it Probable or Unverified rather than Verified.
3. WHEN required input information is absent (e.g., no decision-maker found, no
   project activity found) THEN the system SHALL say so explicitly in the
   relevant output section.
4. WHEN the system's test suite runs THEN it SHALL include at least one test
   case with deliberately incomplete/ambiguous input that asserts the system
   reports missing information instead of inventing it.
5. IF the prospect appears to be a duplicate of an existing CRM record THEN the
   system SHALL surface that instead of creating a new lead.

### Requirement 9 — Minimal UI / API Surface

**User Story:** As a user (founder or salesperson), I want a simple interface to
submit a prospect and view/download results, so that I don't need to use the API
directly for day-to-day use.

#### Acceptance Criteria
1. THE system SHALL expose a documented API (e.g., FastAPI) with endpoints to:
   create a research job, check job status, retrieve the completed brief,
   retrieve the CRM export, and retrieve outreach drafts.
2. THE system SHALL provide a minimal web UI (or equivalent simple interface)
   that allows a non-technical user to submit a prospect, see job status, and
   view/download the brief and CRM export.
3. WHEN a job fails THEN the API and UI SHALL surface a clear, human-readable
   error rather than a raw stack trace or silent failure.
4. WHEN the API is called with invalid input THEN it SHALL return a 4xx response
   with a specific validation message.

### Requirement 10 — Logging, Reliability, and Testing

**User Story:** As the engineer operating this system, I want robust logging,
error handling, and an evaluation suite, so that failures are diagnosable and
the system's behavior is verifiable before it is trusted with real prospects.

#### Acceptance Criteria
1. WHEN any external call (web fetch, LLM call, retrieval call) fails THEN the
   system SHALL retry with backoff up to a configured limit, then fail the job
   with a specific, logged error.
2. WHEN a job runs THEN the system SHALL log each major step (research fetch,
   retrieval, scoring, brief generation, export) with enough detail to
   reconstruct what happened without logging secrets.
3. THE system SHALL read all credentials/API keys from environment variables or
   a secret store; THE system SHALL NOT contain hard-coded credentials.
4. WHEN the test suite runs THEN it SHALL test at least 5 prospects end-to-end,
   including at least 1 clearly poor-fit prospect and at least 2 cases with
   incomplete/ambiguous information.
5. WHEN the test suite runs THEN it SHALL include at least one failure-injection
   test (bad URL, timeout, missing field, or malformed model output) and assert
   the system fails gracefully rather than crashing or returning corrupted
   output.
6. WHEN the test suite runs THEN it SHALL include the score-repeatability test
   from Requirement 4 and the grounding/citation test from Requirement 3.
