# Coextend AI — Project Requirements & Knowledge Base Verification Guide

**Candidate / AI Engineer:** **Sumit Singh** ([@Sumitboii](https://github.com/Sumitboii))  
**Assessment:** AI Automation Engineer — Pilot Project Implementation  
**Organization:** Coextend Global LLP

---


## 1. Executive Summary: Why the Company Asked for This Project

### 1.1 The Business Problem & Founder Bottleneck
**Coextend Global LLP** is a specialized technical pre-construction and engineering company based in Pune, India, serving clients in the **UK, US, and Canada**. They provide high-value technical services:
- **Façade & Cladding Estimating & Quantity Take-Offs**
- **Bill of Quantities (BOQ) & Tender Bid Support**
- **Shop / Fabrication Drawings & 3D BIM Modeling**
- **Commercial Dispute & Variation Support**

**The Core Bottleneck:**  
Façade contracts are high-value (£500,000 to £20M+) with strict 2–3 week bid submission deadlines. The founder currently spends **30 to 45 minutes per prospect** manually scouring LinkedIn, company websites, news feeds, and tender portals to evaluate commercial fit. At 100 leads a month, this burns **50–75 hours of founder time** on manual data gathering rather than closing deals.

### 1.2 Why Company Asked YOU to Make This (The Assessment)
This project is a **paid capability assessment for the AI Automation Engineer role**. The company wants to verify:
1. Can you architect an AI system that solves a real pre-sales bottleneck without hallucinating?
2. Can you separate internal company IP (grounded RAG) from external public web research?
3. Can you implement strict, deterministic mathematical logic (100-point rubric) instead of relying on unpredictable LLM scoring?
4. Can you produce clean, CRM-ready, founder-grade outputs in a 5-day structured milestone timeline?

---

## 2. Company Requirements & Scope Boundaries

### 2.1 Must-Have System Deliverables (From Pilot Brief)
| Component | Required Output | Must-Have? | Why It Was Built This Way |
| :--- | :--- | :---: | :--- |
| **Research Engine** | Structured findings (company snapshot, decision-makers, projects, buying signals) with verified source URLs. | **Yes** | Gives the founder instant commercial context with proof. |
| **Knowledge / RAG Layer** | Vector database over Coextend documents returning source-grounded answers with citations. | **Yes** | Prevents AI from inventing capabilities Coextend does not have. |
| **Lead Scoring Engine** | Deterministic 100-point score breakdown + priority band (High/Medium/Low). | **Yes** | Pure Python code ensures 100% mathematical consistency. |
| **Research Brief** | 3–5 minute decision-ready executive summary. | **Yes** | Enables sales reps to prep for calls in minutes. |
| **CRM-Ready Export** | JSON / CSV payload mapped to HubSpot company/contact/deal schema. | **Yes** | Eliminates manual copy-pasting into the CRM. |
| **Outreach Drafts** | Personalized cold email sequence & LinkedIn connection/pitch drafts. | **Recommended** | Provides customized outreach templates ready for human review. |
| **Simple UI / API** | FastAPI backend + interactive dashboard form and status tracker. | **Yes** | Single interface to submit URLs, monitor progress, and view briefs. |

### 2.2 Prohibited Actions (Strict Safety Guardrails)
- ❌ **Automated LinkedIn Sending / Scraping:** Prohibited to protect Coextend's domain and LinkedIn account reputation. All LinkedIn actions must remain **human-in-the-loop**.
- ❌ **Live Production HubSpot Deployment:** Mock/sandbox export only unless approved.

---

## 3. Detailed Breakdown of Documents Shared & Why We Used Each

The company provided **14 core knowledge base files** and the **Pilot Project Brief**. Below is why each was shared and exactly how it was utilized in our project:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SHARED KNOWLEDGE BASE DOCUMENTS                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  01 - Agent Instructions.docx / .pdf       03 - Marketing Strategy.docx     │
│  01 - Company Profile.docx / .pdf          04 - Email Outreach.docx         │
│  02 - LinkedIn Connection Messages.docx    04 - Research Output Template    │
│  02 - Research Criteria.docx / .pdf        04 - Sales Positioning.docx      │
│  02 - Services.docx / .pdf                 05 - Follow Up Messages.docx     │
│  03 - Company Capabilities.docx / .pdf     05 - Ideal Customer Profile.docx │
│  03 - LinkedIn Pitch Messages.docx         08 - Proposal Templates.docx     │
│  Coextend AI Pilot Project Brief.odt / .pdf                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. `01 - Agent Instructions`
- **What is inside:** The official operational charter for the research agent. Defines evidence classification rules (`[Verified]`, `[Probable]`, `[Unverified]`) and strict anti-hallucination instructions.
- **Why I Used It:** Formed the core **system prompt** and extraction constraint for the LLM. It ensures that if no public evidence is found for a company, the AI explicitly states *"No evidence found"* instead of fabricating answers.

### 2. `01 - Company Profile`
- **What is inside:** Official corporate details of Coextend Global LLP: Pune delivery hub, 10-person headcount, 15+ years combined experience, target markets (UK, US, Canada), core value proposition.
- **Why I Used It:** Ingested into the **Vector RAG layer**. It provides the exact factual baseline about Coextend's identity and prevents the AI from falsely claiming overseas physical registered offices.

### 3. `02 - Services`
- **What is inside:** Detailed breakdown of all 8 service offerings: Façade estimating, Take-offs, BOQ creation, Tender bid support, Shop drawings, BIM modeling, Commercial/variation support, and Software development.
- **Why I Used It:** Used by the RAG engine to **map client needs to Coextend deliverables**. For example, if a prospect bids on curtain walling, the system matches them to Coextend's "Façade & Cladding Take-Off & Estimating" service.

### 4. `02 - Research Criteria`
- **What is inside:** Specifies the 8 research categories to investigate (Company Overview, Decision-Makers, Recent Projects, Tenders, Hiring Signals, Software Tools, Fit Analysis), target executive titles, and source hierarchy.
- **Why I Used It:** Served as the blueprint for the **External Web Research Engine**, dictating the exact search queries, data fields, and decision-maker roles (e.g., Pre-Construction Director, Estimating Manager) to scrape.

### 5. `02 - LinkedIn Connection Messages`
- **What is inside:** 5 structured LinkedIn connection templates tailored by role (Estimating Director, Commercial Lead, Founder) and trigger events (tender win, hiring).
- **Why I Used It:** Integrated into the **Outreach Draft Generator** to produce personalized connection notes under the 300-character LinkedIn limit.

### 6. `03 - Company Capabilities`
- **What is inside:** Deep technical standards (CWCT, BS EN 13830, ASTM, AAMA, CSI MasterFormat), software tools (AutoCAD, Revit, Bluebeam, Planswift), and QA checklists.
- **Why I Used It:** Grounded the brief generator to cite **exact industry standards and software tools** when presenting Coextend's technical credibility to specialist contractors.

### 7. `03 - LinkedIn Pitch Messages`
- **What is inside:** 5 high-converting follow-up pitch messages with explicit calls to action (pilot tender takeoff, capacity overflow support, peer audit).
- **Why I Used It:** Powers the second touchpoint in the generated outreach sequence once a prospect accepts a LinkedIn connection.

### 8. `03 - Marketing Strategy`
- **What is inside:** Strategic positioning, ICP criteria, target geographic segments (UK, US, Canada), key value drivers, and competitive differentiation.
- **Why I Used It:** Ensured all generated hypotheses in the research brief align with Coextend's high-level go-to-market strategy and commercial angles.

### 9. `04 - Email Outreach`
- **What is inside:** 3-step cold email sequences written specifically for Pre-Construction Directors and Estimators facing tender surges.
- **Why I Used It:** Powers the **Email Outreach Generator** to draft tailored 3-email cadences utilizing verified prospect findings.

### 10. `04 - Research Output Template`
- **What is inside:** Standard 11-section brief format: (1) Snapshot, (2) Decision-Makers, (3) Company Research, (4) Projects & Signals, (5) Likely Requirements, (6) Pain Hypotheses, (7) Lead Score, (8) Recommended Approach, (9) Commercial Risks, (10) Next Action, (11) Sources.
- **Why I Used It:** Enforced as the **strict Pydantic JSON Schema** for all generated research briefs, ensuring consistent, founder-ready formatting every time.

### 11. `04 - Sales Positioning`
- **What is inside:** Comprehensive objection-handling matrix, value propositions, and comparative ROI tables (Coextend vs. Hiring In-House vs. Generic Offshore BPO).
- **Why I Used It:** Injected into the brief generation prompt to supply pre-calculated rebuttal angles and commercial pain-point hypotheses.

### 12. `05 - Follow Up Messages`
- **What is inside:** 6 sequential follow-up templates across Days 3, 7, 14, and 21 incorporating tender check-ins, case proof, and polite break-ups.
- **Why I Used It:** Provides follow-up email and message sequences for lead nurturing.

### 13. `05 - Ideal Customer Profile (ICP) & Scoring Rubric`
- **What is inside:** Tier 1/2/3 company definitions, revenue bands (£2M–£50M+), geographic priorities, and the **official 10-factor 100-point lead scoring rubric**.
- **Why I Used It:** The exact formula and logic behind our **Deterministic Python Lead Scoring Engine**.

### 14. `08 - Proposal Templates`
- **What is inside:** 3 commercial engagement structures: (1) Fixed-price per tender/takeoff, (2) Dedicated offshore FTE engineer, (3) Monthly retainer.
- **Why I Used It:** Grounded the "Recommended Next Action" section of the brief with the appropriate commercial contract model.

### 15. `Coextend AI Automation Engineer - Pilot Project Brief`
- **What is inside:** Project scope, 5-day milestone schedule, architecture constraints, forbidden actions, and evaluation rubric.
- **Why I Used It:** The primary engineering specification and master blueprint for designing and building this MVP.

---

## 4. Why We Made the System the Way We Did (Design Rationale)

1. **Two-Pillar Knowledge Separation (Zero Hallucination):**  
   We separated **Internal RAG** (Coextend's static IP) from **External Web Research** (live prospect data). An LLM is never allowed to guess Coextend's capabilities; it can only retrieve approved text with citations.
2. **Deterministic Python Scoring (Zero Probabilistic Variance):**  
   Instead of asking an LLM *"Rate this lead from 0 to 100"*, we coded a pure Python function that computes the score mathematically from verified data points across the 10 rubric factors.
3. **Structured Pydantic Schemas:**  
   Every API endpoint and LLM prompt uses strict Pydantic v2 schemas to ensure schema adherence and prevent malformed data from reaching the UI or CRM.
4. **Human-in-the-Loop Safety:**  
   The system generates drafts and payloads, but a human salesperson always makes the final decision before sending outreach or importing records.

---

## 5. Summary of Artifacts Created

| Artifact / File | Format | Description |
| :--- | :---: | :--- |
| **00 - Coextend AI Master Guide** | PDF | Complete 4-page master architectural & business strategy document. |
| **All 14 Knowledge Docs + Brief** | PDF | High-quality PDF versions of all source DOCX/ODT files. |
| **Project Presentation** | PPTX | 10-slide executive PowerPoint presentation summarizing everything. |
| **This Document** | Markdown | Comprehensive verification and requirements breakdown. |
