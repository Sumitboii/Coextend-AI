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

# Register Arial Unicode TrueType Fonts
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
            self.drawString(40, 760, "Coextend AI — Complete Project Master Guide & Strategy")
            self.drawRightString(572, 760, "Prospect Intelligence System")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 752, 572, 752)
            
        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 42, 572, 42)
        
        self.drawString(40, 30, "Coextend Global LLP — Master Architecture & Project Blueprint")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 30, page_text)
        self.restoreState()

def create_master_guide_pdf(output_path):
    print(f"Generating Master Guide PDF: {output_path}")
    
    primary = colors.HexColor("#1E3A8A")       # Deep Navy
    secondary = colors.HexColor("#0D9488")     # Teal
    accent = colors.HexColor("#D97706")        # Amber Accent
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
        'H1',
        fontName='Arial-Bold',
        fontSize=13.5,
        leading=17,
        textColor=primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'H2',
        fontName='Arial-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        fontName='Arial',
        fontSize=8.5,
        leading=12.5,
        textColor=dark_slate,
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet',
        fontName='Arial',
        fontSize=8.5,
        leading=12.5,
        textColor=dark_slate,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )

    callout_text = ParagraphStyle(
        'Callout',
        fontName='Arial',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E3A8A")
    )
    
    table_head = ParagraphStyle(
        'THead',
        fontName='Arial-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white
    )

    table_cell = ParagraphStyle(
        'TCell',
        fontName='Arial',
        fontSize=7.5,
        leading=10.5,
        textColor=dark_slate
    )

    table_cell_bold = ParagraphStyle(
        'TCellB',
        fontName='Arial-Bold',
        fontSize=7.5,
        leading=10.5,
        textColor=dark_slate
    )
    
    def make_callout(title, text):
        content = [
            Paragraph(f"<b>{title}</b>", ParagraphStyle('CTitle', fontName='Arial-Bold', fontSize=9, leading=12, textColor=primary)),
            Spacer(1, 2),
            Paragraph(text, callout_text)
        ]
        t = Table([[content]], colWidths=[532])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), callout_bg),
            ('BOX', (0,0), (-1,-1), 1, callout_border),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        return t

    flowables = []
    
    # Title Block
    flowables.append(Paragraph("COEXTEND AI — PROSPECT INTELLIGENCE SYSTEM", title_style))
    flowables.append(Paragraph("Complete Master Guide: Architecture, Knowledge Base, Scoring, Workflow & Business Rationale", subtitle_style))
    flowables.append(HRFlowable(width="100%", thickness=1.5, color=primary, spaceAfter=8))
    
    # Executive Summary Card
    exec_summary_text = (
        "<b>System Mission:</b> An AI-assisted prospect intelligence and pre-sales automation engine for "
        "<b>Coextend Global LLP</b>, a specialized technical services firm delivering façade estimating, quantity take-offs, "
        "BOQ preparation, tender support, shop drawings, BIM modeling, and commercial support across the <b>UK, US, and Canada</b>.<br/><br/>"
        "<b>Core Outcome:</b> Transforms a company URL into a <b>decision-ready research brief, deterministic 100-point lead score, "
        "CRM payload, and personalized outreach drafts</b> in under 3 minutes—saving 30–45 minutes of founder time per lead with 0% capability hallucination."
    )
    flowables.append(make_callout("EXECUTIVE CHARTER & VALUE PROPOSITION", exec_summary_text))
    flowables.append(Spacer(1, 6))
    
    # SECTION 1: WHY? WHY THIS PROJECT?
    flowables.append(Paragraph("1. THE 'WHY?' — WHY THIS PROJECT & CORE BUSINESS RATIONALE", h1_style))
    flowables.append(HRFlowable(width="100%", thickness=0.8, color=secondary, spaceAfter=6))
    
    flowables.append(Paragraph(
        "To appreciate this system, you must understand the business problems it solves in the commercial construction and specialist engineering industry:",
        body_style
    ))
    
    flowables.append(Paragraph("A. The Founder's Bottleneck & Time Sink", h2_style))
    flowables.append(Paragraph(
        "Coextend's leadership currently spends <b>30 to 45 minutes manually researching each prospective client</b> before reaching out. They review company websites, LinkedIn leadership, Companies House/filings, tender announcements, and recent projects. At 100 prospects a month, this consumes <b>50–75 hours of high-value founder time</b> on manual searches instead of closing contracts and directing technical teams.",
        body_style
    ))

    flowables.append(Paragraph("B. The Façade & Pre-Construction Reality", h2_style))
    flowables.append(Paragraph(
        "Façade and building envelope contracts represent high-value (£500k to £20M+) packages with strict bid deadlines (often 2–3 weeks). "
        "Generic cold sales pitches fail completely. Commercial and Pre-Construction Directors only engage when outreach demonstrates instant technical credibility—referencing their specific façade systems (curtain walling, unitized systems, rainscreen cladding), engineering standards (CWCT, BS EN, ASTM, CSI MasterFormat), and software workflows (AutoCAD, Revit, Bluebeam).",
        body_style
    ))

    flowables.append(Paragraph("C. Why Generic LLMs Fail", h2_style))
    flowables.append(Paragraph(
        "Generic LLM chatbots fail at prospect intelligence because they: (1) <b>Hallucinate capabilities</b> that Coextend does not provide; (2) <b>Generate inconsistent lead scores</b> based on subjective prompt phrasing; (3) <b>Invent facts</b> about prospect projects and personnel; and (4) <b>Lack citations</b>, making it impossible for a salesperson to verify claims before an executive call.",
        body_style
    ))

    flowables.append(Paragraph("D. The Core Architectural Philosophy: Strict Two-Source Separation", h2_style))
    flowables.append(Paragraph(
        "To prevent hallucination, the architecture strictly separates two knowledge domains:",
        body_style
    ))
    
    arch_table_data = [
        [
            Paragraph("<b>Pillar 1: Internal Knowledge Base (RAG)</b>", table_head),
            Paragraph("<b>Pillar 2: External Research Engine (Live Web)</b>", table_head)
        ],
        [
            Paragraph(
                "• Ingests approved Coextend documents (Services, ICP, Standards, Messaging).<br/>"
                "• Retrieved dynamically via vector similarity with exact document/page citations.<br/>"
                "• <b>Rule:</b> The system can <i>never invent or modify</i> Coextend's capabilities.",
                table_cell
            ),
            Paragraph(
                "• Gathers live public data per prospect (Website, LinkedIn, News, Portfolio).<br/>"
                "• Tags every fact with evidence labels (<b>[Verified]</b>, <b>[Probable]</b>, <b>[Unverified]</b>).<br/>"
                "• <b>Rule:</b> If public evidence is absent, it records <i>'no evidence found'</i>.",
                table_cell
            )
        ]
    ]
    t_arch = Table(arch_table_data, colWidths=[266, 266])
    t_arch.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    flowables.append(t_arch)
    flowables.append(Spacer(1, 8))

    # SECTION 2: WHAT DO WE HAVE TO MAKE?
    flowables.append(Paragraph("2. 'WHAT DO WE HAVE TO MAKE?' — COMPLETE SYSTEM DELIVERABLES", h1_style))
    flowables.append(HRFlowable(width="100%", thickness=0.8, color=secondary, spaceAfter=6))
    
    flowables.append(Paragraph(
        "The project consists of <b>8 core engineering components</b> packaged as a production-grade FastAPI application with an intuitive web dashboard:",
        body_style
    ))
    
    components_data = [
        [
            Paragraph("<b>Component</b>", table_head),
            Paragraph("<b>Technical Specification & Deliverables</b>", table_head),
            Paragraph("<b>Acceptance Standard</b>", table_head)
        ],
        [
            Paragraph("<b>1. Intake & Lifecycle API</b>", table_cell_bold),
            Paragraph("FastAPI endpoints (<code>POST /prospects</code>, <code>GET /prospects/{id}</code>) with Pydantic validation, URL verification, cooldown duplicate check, and asynchronous state machine (<code>pending &rarr; researching &rarr; scoring &rarr; drafting &rarr; complete</code>).", table_cell),
            Paragraph("Immediate <code>job_id</code> return; non-blocking; graceful rejection of bad URLs.", table_cell)
        ],
        [
            Paragraph("<b>2. Knowledge Base (RAG)</b>", table_cell_bold),
            Paragraph("PDF ingestion pipeline with heading-aware chunking, vector database index (ChromaDB/FAISS), metadata tagging (document, section, page), and top-k retrieval with strict internal citations.", table_cell),
            Paragraph("100% citation grounding; zero capability drift; re-ingestion endpoint without code change.", table_cell)
        ],
        [
            Paragraph("<b>3. Web Research Engine</b>", table_cell_bold),
            Paragraph("Automated web scraper and search orchestrator that extracts company overview, regions, target decision-makers, recent tenders, project portfolio, and hiring signals into typed <code>Finding</code> objects.", table_cell),
            Paragraph("Every fact carries source URL; explicit <i>'no evidence found'</i> when missing; evidence labels attached.", table_cell)
        ],
        [
            Paragraph("<b>4. 100-Point Scoring</b>", table_cell_bold),
            Paragraph("<b>Pure Python deterministic logic</b> evaluating the 10 ICP factors (Trade Fit 20, Geography 10, Size 10, Tender Volume 15, Estimating Need 10, Drafting Need 10, Hiring Trigger 10, Decision-Maker Access 5, Outsourcing Readiness 5, Commercial Fit 5).", table_cell),
            Paragraph("Zero LLM math hallucination; 100% repeatability; priority bands (High &ge;70, Med 45-69, Low &lt;45).", table_cell)
        ],
        [
            Paragraph("<b>5. Brief Generator</b>", table_cell_bold),
            Paragraph("LLM assembly engine constrained by JSON schema to generate the standard 11-section Research Output Template (Snapshot, Contacts, Signals, Pain Hypotheses, Score Breakdown, Recommended Approach, Risks).", table_cell),
            Paragraph("3–5 minute read; hypotheses explicitly labeled as hypotheses; clean Markdown/HTML render.", table_cell)
        ],
        [
            Paragraph("<b>6. CRM Export Adapter</b>", table_cell_bold),
            Paragraph("Adapter interface exporting validated prospect findings to HubSpot-compliant JSON and CSV records (Company name, domain, score, priority band, verified contact, recommended service, brief link).", table_cell),
            Paragraph("Duplicate detection against existing records; ready for direct CRM import.", table_cell)
        ],
        [
            Paragraph("<b>7. Outreach Generator</b>", table_cell_bold),
            Paragraph("Generates targeted cold email sequence (3 touchpoints) and LinkedIn connection/pitch drafts using approved message templates, referencing only verified research findings.", table_cell),
            Paragraph("Marked <code>status: 'draft'</code>; <b>zero automated sending</b>; 100% human-in-the-loop control.", table_cell)
        ],
        [
            Paragraph("<b>8. Minimal Web Dashboard</b>", table_cell_bold),
            Paragraph("Clean single-page frontend allowing users to submit company URLs, view live research progress, inspect the brief, download CRM exports, and copy outreach drafts.", table_cell),
            Paragraph("Responsive, intuitive, displays clear failure messages if a website is unreachable.", table_cell)
        ],
    ]
    t_comp = Table(components_data, colWidths=[105, 305, 122])
    t_comp.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_card])
    ]))
    flowables.append(t_comp)
    flowables.append(Spacer(1, 8))

    # SECTION 3: HOW DO WE USE IT?
    flowables.append(Paragraph("3. 'HOW DO WE USE IT?' — END-TO-END OPERATIONAL WORKFLOW", h1_style))
    flowables.append(HRFlowable(width="100%", thickness=0.8, color=secondary, spaceAfter=6))
    
    flowables.append(Paragraph(
        "Operating the system follows a seamless <b>7-step workflow</b> designed for speed and decision clarity:",
        body_style
    ))

    workflow_steps = [
        ("Step 1: Prospect Submission", "The user inputs company name, website URL (e.g. <code>https://apexfaçades.co.uk</code>), and optional contact name into the UI or API."),
        ("Step 2: External Discovery", "The worker scrapes the prospect's website, identifies services, searches LinkedIn for pre-construction leaders, and scans news/tenders for active projects."),
        ("Step 3: Internal RAG Grounding", "The system retrieves matching Coextend capabilities (e.g. unitized façade takeoffs, Bluebeam/Planswift workflows, CWCT compliance) from internal knowledge docs."),
        ("Step 4: Deterministic 100-Point Scoring", "Pure Python code calculates the lead score across 10 factors and assigns a priority band (High, Medium, Low) based on empirical evidence."),
        ("Step 5: Founder Brief Assembly", "The brief generator creates the 11-section research brief with evidence labels (<code>[Verified]</code>, <code>[Probable]</code>, <code>[Unverified]</code>) and source URLs."),
        ("Step 6: CRM Payload Export", "A HubSpot-compatible record is generated in JSON and CSV formats with duplicate detection."),
        ("Step 7: Outreach Review & Dispatch", "The salesperson reviews the 3-minute brief, selects the pre-drafted email or LinkedIn note, refines it, and sends it manually.")
    ]
    for step_title, step_desc in workflow_steps:
        flowables.append(Paragraph(f"<b>{step_title}:</b> {step_desc}", bullet_style))
    
    flowables.append(Spacer(1, 8))

    # SECTION 4: WHAT HELPS US?
    flowables.append(PageBreak())
    flowables.append(Paragraph("4. 'WHAT HELPS US?' — THE COMPLETE KNOWLEDGE BASE DIRECTORY", h1_style))
    flowables.append(HRFlowable(width="100%", thickness=0.8, color=secondary, spaceAfter=6))
    
    flowables.append(Paragraph(
        "The project is powered by <b>14 proprietary knowledge documents</b> and the Pilot Project Brief. Here is what each file contains and how it helps the system:",
        body_style
    ))
    
    docs_data = [
        [
            Paragraph("<b>File / Document</b>", table_head),
            Paragraph("<b>What Is Inside This Document</b>", table_head),
            Paragraph("<b>How It Helps Us in the Project</b>", table_head)
        ],
        [
            Paragraph("<b>01 - Agent Instructions</b>", table_cell_bold),
            Paragraph("Core agent guidelines, evidence standards (Verified vs Probable vs Unverified), and strict no-guess rules.", table_cell),
            Paragraph("Serves as the foundational system prompt / charter for LLM extraction.", table_cell)
        ],
        [
            Paragraph("<b>01 - Company Profile</b>", table_cell_bold),
            Paragraph("Official corporate profile of Coextend Global LLP: Pune hub, 10-person team, UK/US/Canada focus, 15+ yrs experience.", table_cell),
            Paragraph("Grounds all internal RAG facts about Coextend's identity and delivery model.", table_cell)
        ],
        [
            Paragraph("<b>02 - Services</b>", table_cell_bold),
            Paragraph("Comprehensive catalog of 8 services: Façade estimating, Take-offs, BOQs, Tender support, Shop drawings, BIM, Commercial, Software.", table_cell),
            Paragraph("Enables RAG to map client project needs to exact Coextend service packages.", table_cell)
        ],
        [
            Paragraph("<b>02 - Research Criteria</b>", table_cell_bold),
            Paragraph("8 research dimensions, target decision-maker titles, search query patterns, and evidence scoring rules.", table_cell),
            Paragraph("Guides the web crawler on what data to search, extract, and prioritize.", table_cell)
        ],
        [
            Paragraph("<b>02 - LinkedIn Connection Messages</b>", table_cell_bold),
            Paragraph("5 tailored connection message templates categorized by role (Estimating Director, Commercial Lead) and trigger events.", table_cell),
            Paragraph("Supplies templates for drafting personalized connection requests under 300 chars.", table_cell)
        ],
        [
            Paragraph("<b>03 - Company Capabilities</b>", table_cell_bold),
            Paragraph("Engineering standards (CWCT, BS EN, ASTM, CSI MasterFormat), software tools (AutoCAD, Revit, Bluebeam), and QA protocols.", table_cell),
            Paragraph("Allows the brief generator to cite specific standards matching client requirements.", table_cell)
        ],
        [
            Paragraph("<b>03 - LinkedIn Pitch Messages</b>", table_cell_bold),
            Paragraph("5 follow-up pitch angles with calls-to-action (pilot tender takeoff, capacity overflow support, peer audit).", table_cell),
            Paragraph("Provides follow-up pitch drafts once a LinkedIn connection is established.", table_cell)
        ],
        [
            Paragraph("<b>03 - Marketing Strategy</b>", table_cell_bold),
            Paragraph("ICP definition, core value propositions, geographic focus (UK, US, Canada), and positioning pillars.", table_cell),
            Paragraph("Aligns research brief hypotheses with Coextend's strategic market entry angles.", table_cell)
        ],
        [
            Paragraph("<b>04 - Email Outreach</b>", table_cell_bold),
            Paragraph("3 structured multi-touch cold email sequences designed for Pre-Construction Directors facing bid deadlines.", table_cell),
            Paragraph("Powers the Outreach Generator to draft personalized 3-step email sequences.", table_cell)
        ],
        [
            Paragraph("<b>04 - Research Output Template</b>", table_cell_bold),
            Paragraph("Standardized 11-section brief layout: Snapshot, Contacts, Signals, Likely Needs, Hypotheses, Score, Recommendations, Risks.", table_cell),
            Paragraph("Defines the exact JSON schema and UI layout for the founder-ready brief.", table_cell)
        ],
        [
            Paragraph("<b>04 - Sales Positioning</b>", table_cell_bold),
            Paragraph("Objection handling matrix, value propositions, and comparative analysis (Coextend vs In-House vs Generic Offshore BPO).", table_cell),
            Paragraph("Helps generate strong commercial pain-point hypotheses and rebuttal angles.", table_cell)
        ],
        [
            Paragraph("<b>05 - Follow Up Messages</b>", table_cell_bold),
            Paragraph("6 sequential follow-up templates across Day 3, 7, 14, and 21 incorporating tender check-ins and case proof.", table_cell),
            Paragraph("Supplies follow-up messaging sequences for lead nurturing.", table_cell)
        ],
        [
            Paragraph("<b>05 - Ideal Customer Profile (ICP)</b>", table_cell_bold),
            Paragraph("Tier 1/2/3 target definitions, revenue bands (£2M-£50M+), geography, and the <b>10-factor 100-point lead scoring rubric</b>.", table_cell),
            Paragraph("Direct source of truth for the deterministic Python scoring algorithm.", table_cell)
        ],
        [
            Paragraph("<b>08 - Proposal Templates</b>", table_cell_bold),
            Paragraph("3 commercial models: Fixed-price per tender, Dedicated offshore resource (monthly FTE), and On-demand retainer.", table_cell),
            Paragraph("Supplies commercial proposals for the brief's 'Recommended Next Action' section.", table_cell)
        ],
        [
            Paragraph("<b>Pilot Project Brief (ODT)</b>", table_cell_bold),
            Paragraph("5-day milestone roadmap, deliverables, safety boundaries (no automated LinkedIn actions), and evaluation criteria.", table_cell),
            Paragraph("Serves as the engineering roadmap and quality benchmark for MVP delivery.", table_cell)
        ],
    ]
    t_docs = Table(docs_data, colWidths=[115, 245, 172])
    t_docs.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_card])
    ]))
    flowables.append(t_docs)
    flowables.append(Spacer(1, 8))

    # SECTION 5: 100-POINT SCORING RUBRIC BREAKDOWN
    flowables.append(Paragraph("5. THE 100-POINT DETERMINISTIC SCORING RUBRIC", h1_style))
    flowables.append(HRFlowable(width="100%", thickness=0.8, color=secondary, spaceAfter=6))
    
    flowables.append(Paragraph(
        "The scoring engine evaluates 10 weighted factors in pure Python code with zero probabilistic variance:",
        body_style
    ))
    
    rubric_data = [
        [
            Paragraph("<b>Scoring Factor</b>", table_head),
            Paragraph("<b>Max Pts</b>", table_head),
            Paragraph("<b>Scoring Criteria & Banding Rules</b>", table_head)
        ],
        [
            Paragraph("<b>1. Trade & Service Fit</b>", table_cell_bold),
            Paragraph("<b>20 Pts</b>", table_cell_bold),
            Paragraph("Façade/cladding/curtain wall specialist = <b>20</b> | Roofing & envelope = <b>16</b> | Architectural metalwork/glazing = <b>14</b> | Main contractor with façade division = <b>10</b> | General construction/fitout = <b>4</b> | Unrelated trade = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>2. Geography Fit</b>", table_cell_bold),
            Paragraph("<b>10 Pts</b>", table_cell_bold),
            Paragraph("United Kingdom (primary market) = <b>10</b> | United States / Canada = <b>8</b> | Australia / NZ / Ireland = <b>4</b> | Other = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>3. Company Size & Capacity</b>", table_cell_bold),
            Paragraph("<b>10 Pts</b>", table_cell_bold),
            Paragraph("Tier 1 (£20M-£100M+ / 50-250+ staff) = <b>10</b> | Tier 2 (£5M-£20M / 15-50 staff) = <b>8</b> | Tier 3 (£1M-£5M / 5-15 staff) = <b>5</b> | Micro (&lt;5) or Mega (&gt;1000) = <b>2</b>.", table_cell)
        ],
        [
            Paragraph("<b>4. Tender & Project Volume</b>", table_cell_bold),
            Paragraph("<b>15 Pts</b>", table_cell_bold),
            Paragraph("Multiple active major tenders/awards (&ge;3 recent signals) = <b>15</b> | Moderate pipeline (1-2 active projects) = <b>10</b> | Steady pipeline with case studies = <b>6</b> | Stale/no data = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>5. Estimating / Take-off Need</b>", table_cell_bold),
            Paragraph("<b>10 Pts</b>", table_cell_bold),
            Paragraph("High bid volume, fast turnaround need, mentions estimating bottlenecks = <b>10</b> | Regular tender participation = <b>7</b> | General estimating capability = <b>4</b> | In-house fully sufficient = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>6. Drafting / BIM Need</b>", table_cell_bold),
            Paragraph("<b>10 Pts</b>", table_cell_bold),
            Paragraph("Heavy shop/fabrication drawing demand, BIM Level 2 = <b>10</b> | Standard 2D CAD drafting = <b>7</b> | Occasional revisions = <b>4</b> | None = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>7. Hiring / Capacity Trigger</b>", table_cell_bold),
            Paragraph("<b>10 Pts</b>", table_cell_bold),
            Paragraph("Actively recruiting Estimators, QSs, or Façade Designers = <b>10</b> | Recent leadership hires in pre-con = <b>7</b> | Expansion signal = <b>4</b> | None = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>8. Decision-Maker Access</b>", table_cell_bold),
            Paragraph("<b>5 Pts</b>", table_cell_bold),
            Paragraph("Verified Pre-Con / Commercial / Estimating Director = <b>5</b> | Managing Director / Owner = <b>4</b> | General contact = <b>1</b> | None = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>9. Outsourcing Readiness</b>", table_cell_bold),
            Paragraph("<b>5 Pts</b>", table_cell_bold),
            Paragraph("Known history of specialist subconsultants = <b>5</b> | Extended supply chain = <b>3</b> | Neutral/unknown = <b>2</b> | Anti-outsourcing = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>10. Commercial Attractiveness</b>", table_cell_bold),
            Paragraph("<b>5 Pts</b>", table_cell_bold),
            Paragraph("Prompt payment reputation, strong credit health = <b>5</b> | Standard profile = <b>3</b> | Financial risk / legal disputes = <b>0</b>.", table_cell)
        ],
        [
            Paragraph("<b>TOTAL SCORE & PRIORITY BANDS</b>", table_cell_bold),
            Paragraph("<b>100 Pts</b>", table_cell_bold),
            Paragraph("<b>HIGH PRIORITY (&ge; 70 pts):</b> Immediate founder outreach & pilot takeoff pitch.<br/>"
                      "<b>MEDIUM PRIORITY (45–69 pts):</b> Standard email sequence & LinkedIn connection.<br/>"
                      "<b>LOW PRIORITY (&lt; 45 pts):</b> Nurture queue or disqualify.", table_cell_bold)
        ]
    ]
    t_rubric = Table(rubric_data, colWidths=[115, 55, 362])
    t_rubric.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.white, bg_card]),
        ('BACKGROUND', (0,-1), (-1,-1), callout_bg),
    ]))
    flowables.append(t_rubric)
    flowables.append(Spacer(1, 8))

    # SECTION 6: 5-DAY PILOT ROADMAP
    flowables.append(Paragraph("6. 5-DAY PILOT IMPLEMENTATION ROADMAP", h1_style))
    flowables.append(HRFlowable(width="100%", thickness=0.8, color=secondary, spaceAfter=6))
    
    roadmap_data = [
        [
            Paragraph("<b>Day / Milestone</b>", table_head),
            Paragraph("<b>Core Tasks & Implementation Focus</b>", table_head),
            Paragraph("<b>End-of-Day Deliverable</b>", table_head)
        ],
        [
            Paragraph("<b>Day 1</b>", table_cell_bold),
            Paragraph("Understand brief, establish repository skeleton (<code>/api</code>, <code>/engine</code>, <code>/knowledge</code>, <code>/scoring</code>, <code>/tests</code>), create Pydantic models, and write architecture note.", table_cell),
            Paragraph("Architecture note (<code>docs/architecture.md</code>) + working FastAPI skeleton.", table_cell)
        ],
        [
            Paragraph("<b>Day 2</b>", table_cell_bold),
            Paragraph("Build internal RAG vector indexing over Coextend PDFs + implement public web research scraper with structured extraction and evidence labeling.", table_cell),
            Paragraph("Working research output tested on 3 live prospects with source URLs and citations.", table_cell)
        ],
        [
            Paragraph("<b>Day 3</b>", table_cell_bold),
            Paragraph("Implement pure Python 100-point lead scoring engine, structured Research Brief assembler, and HubSpot-compatible CRM export adapter.", table_cell),
            Paragraph("Deterministic scoring unit tests + valid JSON/CSV exports generated for test prospects.", table_cell)
        ],
        [
            Paragraph("<b>Day 4</b>", table_cell_bold),
            Paragraph("Add outreach draft generation (email/LinkedIn), build minimal web UI dashboard, implement structured logging, retry backoffs, and failure recovery.", table_cell),
            Paragraph("End-to-end demo candidate build running locally with functional UI and error handling.", table_cell)
        ],
        [
            Paragraph("<b>Day 5</b>", table_cell_bold),
            Paragraph("End-to-end evaluation on 5 prospects (including poor-fit & ambiguous), write test report, polish documentation, create run instructions and cost estimates.", table_cell),
            Paragraph("Final production-ready repository + README + test evaluation report + demo walk-through.", table_cell)
        ]
    ]
    t_road = Table(roadmap_data, colWidths=[60, 312, 160])
    t_road.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_card])
    ]))
    flowables.append(t_road)
    flowables.append(Spacer(1, 10))
    
    # Final Sign-off Box
    sign_off_text = (
        "<b>Summary & Status:</b> All 14 foundational DOCX documents and the pilot brief ODT have been converted into "
        "crisp, publication-ready PDF files. This Master Guide provides the definitive system architecture, scoring rubric, "
        "workflow, and knowledge base mapping required to build and deploy the Coextend AI Prospect Intelligence MVP."
    )
    flowables.append(make_callout("COEXTEND AI PILOT READINESS VERIFIED", sign_off_text))

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=54,
        bottomMargin=54
    )
    
    doc.build(flowables, canvasmaker=NumberedCanvas)
    print(f"Successfully generated Master Guide PDF at {output_path}")

if __name__ == "__main__":
    out_file = r"C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI\00 - Coextend AI - Complete Project Master Guide & Strategy.pdf"
    create_master_guide_pdf(out_file)
