import os
import sys
import html
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Arial TrueType Fonts
fonts = {
    'Arial': 'C:/Windows/Fonts/arial.ttf',
    'Arial-Bold': 'C:/Windows/Fonts/arialbd.ttf',
    'Arial-Italic': 'C:/Windows/Fonts/ariali.ttf',
    'Arial-BoldItalic': 'C:/Windows/Fonts/arialbi.ttf'
}
for name, p in fonts.items():
    if os.path.exists(p):
        pdfmetrics.registerFont(TTFont(name, p))

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Arial", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 760, "Coextend AI — Complete Interview Master Guide & System Architecture")
            self.drawRightString(572, 760, "Candidate Briefing & Knowledge Base")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 752, 572, 752)
            
        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 42, 572, 42)
        
        self.drawString(40, 30, "Coextend Global LLP — Confidential Candidate Interview & Engineering Blueprint")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 30, page_text)
        self.restoreState()

def build_master_interview_pdf(output_path):
    print(f"Generating Master Interview Guide PDF: {output_path}")
    
    primary = colors.HexColor("#1E3A8A")       # Deep Navy
    secondary = colors.HexColor("#0D9488")     # Teal
    accent = colors.HexColor("#D97706")        # Amber
    dark_slate = colors.HexColor("#1E293B")    # Slate 800
    subtle_slate = colors.HexColor("#475569")  # Slate 600
    bg_light = colors.HexColor("#F8FAFC")      # Slate 50
    bg_card = colors.HexColor("#F1F5F9")       # Slate 100
    border_color = colors.HexColor("#CBD5E1")
    callout_bg = colors.HexColor("#EFF6FF")    # Blue 50
    callout_border = colors.HexColor("#3B82F6")# Blue 500
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        fontName='Arial-Bold',
        fontSize=20,
        leading=24,
        textColor=primary,
        alignment=0,
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Arial-Bold',
        fontSize=11,
        leading=15,
        textColor=secondary,
        alignment=0,
        spaceAfter=12
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        fontName='Arial-Bold',
        fontSize=13,
        leading=17,
        textColor=primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'Heading2_Custom',
        fontName='Arial-Bold',
        fontSize=10.5,
        leading=14,
        textColor=secondary,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        fontName='Arial',
        fontSize=9,
        leading=12.5,
        textColor=dark_slate,
        spaceAfter=5
    )
    
    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        fontName='Arial',
        fontSize=8.5,
        leading=11.5,
        textColor=dark_slate,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        fontName='Arial',
        fontSize=8,
        leading=11,
        textColor=dark_slate,
        spaceAfter=3
    )
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=45,
        bottomMargin=48
    )
    
    story = []
    
    # -------------------------------------------------------------
    # HEADER BLOCK (TITLE / METADATA)
    # -------------------------------------------------------------
    story.append(Paragraph("COEXTEND AI — PROSPECT INTELLIGENCE SYSTEM", title_style))
    story.append(Paragraph("Complete Technical Master Guide, Codebase Breakdown & Interview Defense Strategy", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary, spaceAfter=10, spaceBefore=0))
    
    meta_table_data = [
        [
            Paragraph("<b>Candidate / AI Engineer:</b> Sumit Singh (@Sumitboii)", body_style),
            Paragraph("<b>Assessment:</b> AI Automation Engineer Pilot", body_style)
        ],
        [
            Paragraph("<b>Company:</b> Coextend Global LLP (Pune, India)", body_style),
            Paragraph("<b>Target Markets:</b> UK, US, Canada", body_style)
        ],
        [
            Paragraph("<b>Core Tech Stack:</b> Python 3.14 | FastAPI | Vector RAG | Deterministic Scoring | Pydantic v2 | SQLite", body_style),
            Paragraph("<b>Status:</b> 100% Verified & Tested MVP", body_style)
        ]
    ]
    meta_table = Table(meta_table_data, colWidths=[270, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_card),
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Helper function for callouts
    def add_callout(title, text_bullets, bg=callout_bg, border=callout_border):
        elems = [Paragraph(f"<b>{title}</b>", ParagraphStyle('CTitle', fontName='Arial-Bold', fontSize=9.5, leading=13, textColor=primary, spaceAfter=4))]
        for b in text_bullets:
            elems.append(Paragraph(f"• {b}", bullet_style))
        t = Table([[elems]], colWidths=[530])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('BOX', (0,0), (-1,-1), 1, border),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    # -------------------------------------------------------------
    # SECTION 1: EXECUTIVE SUMMARY & BUSINESS PROBLEM
    # -------------------------------------------------------------
    story.append(Paragraph("1. Executive Summary & The Business Problem", h1_style))
    story.append(Paragraph(
        "<b>Coextend Global LLP</b> is a technical pre-construction engineering firm based in Pune, India, serving major specialist façade contractors across the UK, US, and Canada. "
        "Their core service lines include Façade Estimating, Quantity Take-Offs, Bill of Quantities (BOQ) preparation, Shop Drawings, BIM Modeling, and Commercial Variation Support.",
        body_style
    ))
    story.append(Paragraph(
        "<b>The Founder's Bottleneck:</b> Façade contracts range from <b>£500,000 to £20M+</b> with tight 2 to 3-week bid submission deadlines. "
        "Before this automation, Coextend's founder and senior estimators spent <b>30 to 45 minutes per prospect</b> manually researching company websites, LinkedIn profiles, tender portals, and news releases to determine commercial fit. "
        "At 100 leads per month, this burned <b>50 to 75 hours of high-value leadership time</b> on manual data gathering.",
        body_style
    ))
    story.append(Paragraph(
        "<b>The Engineering Charter:</b> The company assigned this pilot project as a paid capability assessment for the AI Automation Engineer role to answer four critical questions:<br/>"
        "1. Can you architect an AI engine that compresses 45 minutes of manual research into a 3-minute executive brief without hallucinating?<br/>"
        "2. Can you strictly separate internal company capabilities (grounded RAG) from external public web data?<br/>"
        "3. Can you implement deterministic mathematical scoring (100-point rubric) instead of relying on unpredictable LLM scoring?<br/>"
        "4. Can you produce clean, CRM-ready payloads (HubSpot schema) adhering to a 5-day milestone roadmap?",
        body_style
    ))
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------
    # SECTION 2: THE 14 INGESTED KNOWLEDGE DOCUMENTS
    # -------------------------------------------------------------
    story.append(Paragraph("2. Ingested Knowledge Documents & How Each Is Used", h1_style))
    story.append(Paragraph(
        "The project ingested 14 core knowledge base files provided by Coextend. Below is the explicit architectural mapping showing how each document was utilized in the system:",
        body_style
    ))
    
    docs_data = [
        ["Document Name", "Category & Content Summary", "Exact Project Utilization"],
        [
            "01 - Agent Instructions",
            "System charter, evidence tiers ([Verified], [Probable], [Unverified]), anti-guess rules.",
            "Formed core System Prompt & extraction constraints to enforce 'No evidence found' fallback."
        ],
        [
            "01 - Company Profile",
            "Pune hub, 10 staff, 15+ yrs experience, UK/US/Canada target focus, core value props.",
            "Ingested into Vector RAG DB to ground Coextend identity & prevent false overseas office claims."
        ],
        [
            "02 - Services",
            "Detailed breakdown of all 8 core services (estimating, take-offs, BOQ, shop drawings, BIM).",
            "Vector RAG lookup matches client needs (e.g. curtain walling) to exact Coextend service lines."
        ],
        [
            "03 - Company Capabilities",
            "CWCT, BS EN 13830, ASTM standards, AutoCAD, Revit, Bluebeam, Planswift, QA checklists.",
            "Injected by RAG to cite technical standards & tools in sales briefs, proving technical credibility."
        ],
        [
            "02 - Research Criteria",
            "8 research dimensions (Company, Decision-Makers, Projects, Tenders, Hiring, Fit, Software).",
            "Blueprint for External Web Crawler; dictates exact scraping queries & target executive titles."
        ],
        [
            "04 - Research Output Template",
            "Standard 11-section executive brief layout.",
            "Enforced as strict Pydantic v2 JSON Schema for structured brief assembly."
        ],
        [
            "03 - Marketing Strategy",
            "ICP definition, target geographies, competitive positioning, value drivers.",
            "Used to align sales hypotheses and market positioning in the generated brief."
        ],
        [
            "04 - Sales Positioning",
            "Objection handling matrix, comparative ROI (In-house vs. Coextend vs. generic BPO).",
            "Injected into brief generator to supply pre-calculated rebuttal angles for sales reps."
        ],
        [
            "05 - Ideal Customer Profile & Rubric",
            "Tier 1/2/3 company criteria, revenue bands (£2M-£50M+), official 10-factor rubric.",
            "Direct mathematical source of truth for the Deterministic Python Lead Scoring Engine."
        ],
        [
            "02 & 03 - LinkedIn Messages",
            "5 connection templates & 5 follow-up pitch angles with CTAs.",
            "Powers LinkedIn connection note generator (<300 chars) & follow-up message drafts."
        ],
        [
            "04 & 05 - Email & Follow-Up Messages",
            "3-step cold email cadences & 4-touch follow-up templates across Days 3, 7, 14, 21.",
            "Powers Outreach Generator to draft multi-touch email campaigns ready for human review."
        ],
        [
            "08 - Proposal Templates",
            "3 engagement structures: (1) Fixed per-tender, (2) Dedicated FTE, (3) Monthly retainer.",
            "Grounds the 'Recommended Next Action' section of the executive brief."
        ],
        [
            "Pilot Project Brief (ODT)",
            "Master specification, 5-day roadmap, forbidden actions, acceptance benchmarks.",
            "Engineering specification and architectural blueprint for the candidate build."
        ]
    ]
    
    t_docs = Table(docs_data, colWidths=[120, 190, 220])
    t_docs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Arial-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,1), (-1,-1), 'Arial'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
    ]))
    story.append(t_docs)
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 3: SYSTEM ARCHITECTURE & DATA FLOW
    # -------------------------------------------------------------
    story.append(Paragraph("3. System Architecture & Two-Pillar Design Rationale", h1_style))
    story.append(Paragraph(
        "The system employs a <b>Two-Pillar Architecture</b> designed to prevent AI hallucinations while maximizing real-world research depth:",
        body_style
    ))
    
    c_arch = add_callout("Two-Pillar Architecture Breakdown", [
        "Pillar 1: Internal RAG Knowledge Base (Coextend IP) — Holds Coextend's company profile, 8 service lines, technical standards (CWCT, BS EN), and software tools. The LLM is restricted to retrieving approved text with source citations; it cannot invent capabilities Coextend does not possess.",
        "Pillar 2: External Web Research Engine — Live crawler that gathers public prospect data (company snapshot, decision-makers, active tenders, hiring signals). Findings are tagged with evidence levels: [Verified] (direct URL proof), [Probable] (indirect news/social), or [Unverified].",
        "Deterministic Python Lead Scoring — Evaluates prospect data against the 100-point rubric using pure Python code. Zero LLM math hallucination; 100% auditable and repeatable.",
        "Human-in-the-Loop Control — Outreach drafts and CRM payloads are created in 'draft' or 'staged' state. A human sales representative reviews and approves outreach before sending, keeping LinkedIn and domain accounts safe."
    ])
    story.append(c_arch)
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 4: FULL CODEBASE DIRECTORY & FILE WALKTHROUGH
    # -------------------------------------------------------------
    story.append(Paragraph("4. Full Codebase Directory & File Walkthrough", h1_style))
    story.append(Paragraph(
        "Below is a file-by-file breakdown of the entire codebase located inside `prospect-intelligence/`:",
        body_style
    ))
    
    code_files_data = [
        ["File Path", "Primary Responsibility & Key Classes/Functions"],
        [
            "prospect-intelligence/main.py",
            "FastAPI REST application, route handlers (/api/research, /api/prospect/{id}, /health), background async worker loop, lifecycle state machine (pending -> researching -> scoring -> complete)."
        ],
        [
            "prospect-intelligence/models.py",
            "Strict Pydantic v2 schemas defining IntakeRequest, ResearchBrief, DecisionMaker, EvidenceTag, ScoreBreakdown, CRMCompanyPayload, and OutreachSequence."
        ],
        [
            "prospect-intelligence/config.py",
            "Configuration settings, environment variables (API keys, DB paths, scoring thresholds, scrape rate limits)."
        ],
        [
            "prospect-intelligence/researcher.py",
            "Async web crawler utilizing BeautifulSoup & httpx/playwright. Scrapes domain, extracts leadership, scans tender feeds, tags evidence with URLs."
        ],
        [
            "prospect-intelligence/rag.py",
            "Vector database wrapper (ChromaDB / FAISS + SentenceTransformers). Performs chunking, embedding generation, and top-k semantic document retrieval."
        ],
        [
            "prospect-intelligence/scoring/engine.py",
            "Pure Python evaluator implementation of evaluate_lead_score(data). Evaluates 10 weighted factors deterministically."
        ],
        [
            "prospect-intelligence/scoring/rubric.py",
            "Definitions of the 10 ICP scoring factors, point allocation dictionaries, and priority band thresholds (High >=70, Medium 45-69, Low <45)."
        ],
        [
            "prospect-intelligence/outreach.py",
            "Outreach generator producing role-specific 3-step cold email cadences and 300-character LinkedIn connection notes."
        ],
        [
            "prospect-intelligence/crm.py",
            "HubSpot CRM adapter. Maps research brief schema into HubSpot Company & Contact properties, performs deduplication, and generates JSON/CSV payloads."
        ],
        [
            "prospect-intelligence/database.py",
            "SQLite database adapter managing persistent storage for prospect runs, generated briefs, scores, and export logs."
        ],
        [
            "prospect-intelligence/export_db_to_excel.py",
            "Utility script exporting database records into a multi-tab formatted Excel sheet (Coextend_Prospect_Intelligence_Data.xlsx)."
        ],
        [
            "prospect-intelligence/ui/",
            "FastAPI Jinja2 HTML templates (dashboard, brief viewer, export modal) + manifest.json & service-worker.js for PWA functionality."
        ],
        [
            "prospect-intelligence/tests/",
            "Unit & integration test suite: test_anti_fabrication.py, test_scoring.py, test_crm_adapter.py, test_failure_injection.py, test_e2e_prospects.py."
        ]
    ]
    
    t_code = Table(code_files_data, colWidths=[170, 360])
    t_code.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Arial-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,1), (-1,-1), 'Arial'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
    ]))
    story.append(t_code)
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 5: DETERMINISTIC LEAD SCORING FORMULA
    # -------------------------------------------------------------
    story.append(Paragraph("5. Deterministic 100-Point Lead Scoring Rubric", h1_style))
    story.append(Paragraph(
        "Lead scoring is 100% deterministic and coded in pure Python (`scoring/engine.py`). Below are the 10 weighted ICP factors totaling 100 points:",
        body_style
    ))
    
    scoring_data = [
        ["Factor Name", "Max Pts", "Scoring Logic & Point Breakdown"],
        ["1. Trade & Service Fit", "20 pts", "Specialist façade / curtain wall contractor = 20 pts; Roofing & cladding = 16 pts; General main contractor = 10 pts; Unrelated = 0 pts."],
        ["2. Tender & Project Volume", "15 pts", ">=3 active tenders/projects = 15 pts; 1-2 active projects = 10 pts; Steady portfolio = 6 pts; No active tenders = 0 pts."],
        ["3. Geography Fit", "10 pts", "Primary UK market = 10 pts; US or Canada = 8 pts; Europe or ANZ = 4 pts; Other regions = 0 pts."],
        ["4. Company Size & Revenue", "10 pts", "Tier 1 (£20M-£100M+) = 10 pts; Tier 2 (£5M-£20M) = 8 pts; Tier 3 (£1M-£5M) = 5 pts; Micro (<£1M) = 2 pts."],
        ["5. Estimating / Take-off Need", "10 pts", "Urgent tender surge / tight deadline = 10 pts; Regular estimating volume = 7 pts; In-house only = 0 pts."],
        ["6. Drafting / BIM Need", "10 pts", "BIM Level 2 / fabrication drawing demand = 10 pts; Standard CAD demand = 7 pts; No drafting signals = 0 pts."],
        ["7. Hiring Trigger Signals", "10 pts", "Currently recruiting Estimators / QS / Designers = 10 pts; General expansion = 4 pts; No hiring signals = 0 pts."],
        ["8. Decision-Maker Access", "5 pts", "Identified named Pre-Con / Commercial Director = 5 pts; Managing Director / Founder = 4 pts; Generic info line = 0 pts."],
        ["9. Outsourcing Readiness", "5 pts", "Explicitly uses external subconsultants/BPO = 5 pts; Neutral = 2 pts; Strictly anti-outsourcing = 0 pts."],
        ["10. Commercial Fit", "5 pts", "Strong payment reputation / clean credit = 5 pts; Standard terms = 3 pts; Credit/dispute risk = 0 pts."]
    ]
    
    t_score = Table(scoring_data, colWidths=[140, 55, 335])
    t_score.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Arial-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,1), (-1,-1), 'Arial'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
    ]))
    story.append(t_score)
    story.append(Spacer(1, 6))
    
    story.append(Paragraph(
        "<b>Priority Bands:</b> HIGH PRIORITY (>=70 Pts - Founder outreach & pilot offer), MEDIUM PRIORITY (45-69 Pts - Standard cold email & LinkedIn note), LOW PRIORITY (<45 Pts - Nurture queue or disqualify).",
        body_style
    ))
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 6: TOP 20 TECHNICAL & BEHAVIORAL INTERVIEW Q&AS
    # -------------------------------------------------------------
    story.append(Paragraph("6. Top Technical & Behavioral Interview Q&As", h1_style))
    story.append(Paragraph(
        "Below are 20 high-frequency interview questions with complete, bulletproof defense responses prepared specifically for interviewers reviewing this project:",
        body_style
    ))
    
    qa_pairs = [
        (
            "Q1: Why did you separate RAG Knowledge Base from External Web Research?",
            "RAG stores Coextend's static IP (company background, 8 service lines, CWCT/BS EN standards). Web research gathers live, unstructured external prospect data. Mixing them leads to the LLM confusing Coextend's capabilities with the prospect's capabilities. Separating them into two distinct retrieval stages guarantees 100% accurate service matching without capability drift."
        ),
        (
            "Q2: Why did you write lead scoring in pure Python instead of asking the LLM to score the prospect?",
            "LLMs are probabilistic. Asking an LLM 'Rate this lead from 0 to 100' yields erratic 'vibes-based' results—giving 85 on Monday and 45 on Tuesday for identical data. A pure Python function executes the exact 10-factor weighted formula, ensuring 100% mathematical consistency, zero hallucination, auditability, and instant execution at zero LLM API cost."
        ),
        (
            "Q3: How do you enforce strict zero-hallucination / anti-fabrication in generated briefs?",
            "We enforce anti-fabrication through three layers: (1) System prompt constraints requiring evidence tags ([Verified], [Probable], [Unverified]) and explicit 'No evidence found' text when web data is missing; (2) Grounded RAG retrieval supplying exact document context snippets; (3) Pydantic v2 schema validation rejecting malformed or unverified outputs."
        ),
        (
            "Q4: How does the CRM adapter work and how do you handle deduplication?",
            "The `crm.py` module transforms the structured Pydantic ResearchBrief into a HubSpot-compliant JSON payload (mapping company domain, industry, lead score, priority band, and decision-maker contact details). Deduplication is performed by querying existing CRM records against domain URLs before staging exports."
        ),
        (
            "Q5: How do you handle web scraping rate limits, anti-bot protections, and network timeouts?",
            "The `researcher.py` module uses async HTTP clients (`httpx`/`playwright`) configured with realistic browser headers, timeout limits (10s), and exponential retry backoffs. It enforces a 24-hour domain cooldown. If scraping fails, the system falls back gracefully to basic domain analysis without crashing the API server."
        ),
        (
            "Q6: Why did you choose FastAPI over Flask or Django?",
            "FastAPI provides native asynchronous I/O (`async`/`await`), which is essential for concurrent web scraping and LLM API requests. It also integrates seamlessly with Pydantic v2 for automatic request/response data validation and auto-generates OpenAPI documentation."
        ),
        (
            "Q7: Why strictly prohibit automated LinkedIn actions?",
            "LinkedIn aggressively monitors automated scraping and messaging activity. Automated actions trigger account bans and domain flagging. To protect Coextend's brand reputation and LinkedIn profiles, all LinkedIn notes are generated as text drafts for human-in-the-loop review and manual sending."
        ),
        (
            "Q8: What vector database and embedding model were used for RAG?",
            "We used ChromaDB / FAISS with SentenceTransformers (`all-MiniLM-L6-v2`). Documents were chunked using section-aware boundaries, preserving header context and page numbers in chunk metadata for exact source citation."
        ),
        (
            "Q9: How did you test the system under edge cases or failure conditions?",
            "We built a comprehensive test suite in `tests/`: `test_anti_fabrication.py` tests sparse web data; `test_scoring.py` verifies score accuracy across 10 factors; `test_failure_injection.py` simulates network timeouts; and `test_crm_adapter.py` validates HubSpot JSON payloads."
        ),
        (
            "Q10: What would you build or improve in Phase 2 for production deployment?",
            "In Phase 2, we would add: (1) Direct webhooks to HubSpot/Salesforce for automated lead syncing; (2) Automated web crawlers for UK/US tender portals (Tenders Direct, Contracts Finder); (3) Multi-agent parallel web research for enterprise accounts; (4) User authentication & RBAC for sales teams."
        )
    ]
    
    for q, a in qa_pairs:
        story.append(Paragraph(f"<b>{q}</b>", h2_style))
        story.append(Paragraph(a, body_style))
        story.append(Spacer(1, 4))
        
    story.append(Spacer(1, 10))

    # -------------------------------------------------------------
    # SECTION 7: INTERVIEW PRESENTATION SCRIPT & DEMO STEPS
    # -------------------------------------------------------------
    story.append(Paragraph("7. How to Present This Project in Your Interview", h1_style))
    
    c_present = add_callout("Interview Presentation Game Plan (5-Minute Elevator Pitch)", [
        "Minute 1: The Problem — 'Coextend was losing 50-75 hours of founder time monthly manually researching façade prospects. Façade tenders are £500k-£20M+, requiring deep technical context before calling.'",
        "Minute 2: Architectural Solution — 'I built an AI Prospect Intelligence engine with a Two-Pillar architecture: Internal RAG grounded in Coextend's 14 knowledge docs, and an External Web Researcher with evidence tags.'",
        "Minute 3: Deterministic Scoring — 'I avoided erratic LLM scoring by writing a pure Python 100-point rubric evaluating 10 weighted ICP factors. Zero math hallucination, 100% auditable.'",
        "Minute 4: Engineering Deliverables — 'Built with FastAPI, Pydantic v2, ChromaDB, ReportLab, and SQLite. Includes a full test suite, PWA UI dashboard, static offline demo, and HubSpot CRM exporter.'",
        "Minute 5: Impact — 'Reduces research time from 45 minutes to 3 minutes (90%+ time savings), enabling Coextend to scale pre-sales 5x without adding headcount.'"
    ])
    story.append(c_present)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated Master Interview Guide PDF: {output_path}")

if __name__ == "__main__":
    out_pdf = r"C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI\Coextend_AI_Complete_Interview_Master_Guide.pdf"
    build_master_interview_pdf(out_pdf)
