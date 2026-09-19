import os
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

fonts = {
    'Arial': 'C:/Windows/Fonts/arial.ttf',
    'Arial-Bold': 'C:/Windows/Fonts/arialbd.ttf',
    'Arial-Italic': 'C:/Windows/Fonts/ariali.ttf',
    'Arial-BoldItalic': 'C:/Windows/Fonts/arialbi.ttf'
}
for name, p in fonts.items():
    if os.path.exists(p):
        pdfmetrics.registerFont(TTFont(name, p))

def generate_presentation_pdf(output_path):
    # Landscape letter: 792 x 612 pt
    doc = SimpleDocTemplate(
        output_path,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    NAVY = colors.HexColor("#1E3A8A")
    TEAL = colors.HexColor("#0D9488")
    SLATE = colors.HexColor("#1E293B")
    CARD_BG = colors.HexColor("#F1F5F9")
    BLUE_LIGHT = colors.HexColor("#EFF6FF")
    BORDER_BLUE = colors.HexColor("#3B82F6")
    BORDER_GRAY = colors.HexColor("#CBD5E1")
    
    styles = getSampleStyleSheet()
    
    s_title = ParagraphStyle('STitle', fontName='Arial-Bold', fontSize=20, leading=24, textColor=NAVY, spaceAfter=2)
    s_sub = ParagraphStyle('SSub', fontName='Arial-Bold', fontSize=10.5, leading=13, textColor=TEAL, spaceAfter=10)
    s_card_t = ParagraphStyle('SCardT', fontName='Arial-Bold', fontSize=10, leading=12, textColor=NAVY, spaceAfter=4)
    s_card_b = ParagraphStyle('SCardB', fontName='Arial', fontSize=8, leading=10.5, textColor=SLATE, spaceAfter=2)
    
    def make_slide_card(title, bullets, width=228, height=390, bg=CARD_BG, border=BORDER_GRAY):
        content = [Paragraph(f"<b>{title}</b>", s_card_t), Spacer(1, 3)]
        for b in bullets:
            content.append(Paragraph(f"• {b}", s_card_b))
        t = Table([[content]], colWidths=[width])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg),
            ('BOX', (0,0), (-1,-1), 1, border),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        return t

    slides_content = []
    
    # Slide 1: Title
    t1 = [
        Paragraph("COEXTEND AI — PROSPECT INTELLIGENCE MVP", ParagraphStyle('HeroT', fontName='Arial-Bold', fontSize=24, leading=28, textColor=NAVY)),
        Spacer(1, 4),
        Paragraph("AI Automation Engineer Candidate Interview Presentation & Blueprint", ParagraphStyle('HeroS', fontName='Arial-Bold', fontSize=12, leading=15, textColor=TEAL)),
        Spacer(1, 16),
        Paragraph("<b>Candidate / AI Engineer:</b> Sumit Singh (@Sumitboii)", ParagraphStyle('HeroM', fontName='Arial-Bold', fontSize=10, leading=14, textColor=SLATE)),
        Paragraph("<b>Company:</b> Coextend Global LLP (Pune, India | Target Markets: UK, US & Canada)", ParagraphStyle('HeroM1', fontName='Arial', fontSize=10, leading=14, textColor=SLATE)),
        Paragraph("<b>Assessment Charter:</b> Paid Capability Assessment for AI Automation Engineer Role", ParagraphStyle('HeroM2', fontName='Arial', fontSize=10, leading=14, textColor=SLATE)),
        Paragraph("<b>Core Stack:</b> Python 3.14 | FastAPI | Vector RAG | Deterministic 100-Pt Scoring | Pydantic v2", ParagraphStyle('HeroM3', fontName='Arial-Bold', fontSize=10, leading=14, textColor=NAVY)),
    ]
    t_box1 = Table([[t1]], colWidths=[720])
    t_box1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BLUE_LIGHT),
        ('BOX', (0,0), (-1,-1), 2, NAVY),
        ('TOPPADDING', (0,0), (-1,-1), 35),
        ('BOTTOMPADDING', (0,0), (-1,-1), 35),
        ('LEFTPADDING', (0,0), (-1,-1), 25),
        ('RIGHTPADDING', (0,0), (-1,-1), 25),
    ]))
    slides_content.append(t_box1)
    slides_content.append(PageBreak())

    # Slide 2: Business Problem
    slides_content.append(Paragraph("Slide 2: Business Problem & Pre-Sales Founder Bottleneck", s_title))
    slides_content.append(Paragraph("WHY COEXTEND ASKED FOR THIS PROJECT", s_sub))
    c1 = make_slide_card("1. The Founder's Bottleneck", [
        "Founder spends 30–45 mins per lead on manual research across LinkedIn, websites & feeds.",
        "At 100 leads/month, burns 50–75 hours of high-value founder time.",
        "Manual searches create qualification inconsistencies.",
        "Goal: Compress 45 mins into a 3-min decision-ready brief."
    ], width=230)
    c2 = make_slide_card("2. High-Stakes Façade Market", [
        "Façade tenders range from £500k to £20M+ with strict 2-3 wk deadlines.",
        "Generic cold pitches fail and ruin credibility.",
        "Outreach must cite specific CWCT, BS EN 13830, ASTM & software tools.",
        "Goal: Arm sales team with exact technical pain points."
    ], width=230)
    c3 = make_slide_card("3. The Engineering Assessment", [
        "Paid capability assessment for AI Automation Engineer role.",
        "Tests software architecture, RAG grounding, and deterministic math.",
        "Evaluates 5-day delivery roadmap execution.",
        "Goal: Deliver a clean, audited, and tested candidate build."
    ], width=230, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_row2 = Table([[c1, c2, c3]], colWidths=[240, 240, 240])
    t_row2.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row2)
    slides_content.append(PageBreak())

    # Slide 3: Why Generic AI Fails
    slides_content.append(Paragraph("Slide 3: Why Generic AI Prompts Fail & Architectural Solution", s_title))
    slides_content.append(Paragraph("THE ENGINEERING PROBLEM & ARCHITECTURAL SOLUTION", s_sub))
    c1 = make_slide_card("1. Hallucinated Capabilities", [
        "Generic LLMs confuse civil drafting with specialist façade takeoffs.",
        "AI promises services Coextend doesn't offer (e.g., structural design).",
        "Uses US CSI codes for UK contractors who need Uniclass/NRM2."
    ], width=350)
    c2 = make_slide_card("2. Erratic 'Vibes' Scoring", [
        "LLMs give 85/100 on Monday and 45/100 on Tuesday for the same data.",
        "Subjective scoring breaks CRM pipeline prioritization.",
        "Probabilistic math cannot be audited or trusted."
    ], width=350)
    c3 = make_slide_card("3. Fabricated Facts", [
        "LLMs invent contract wins and assume non-existent project scopes.",
        "Zero audit trail leaves sales reps vulnerable on calls."
    ], width=350)
    c4 = make_slide_card("4. Two-Pillar Solution", [
        "Pillar 1: Internal RAG grounded ONLY in approved Coextend IP.",
        "Pillar 2: Live Web Research with [Verified] / [Probable] tags.",
        "Scoring: 100% pure Python code—zero LLM math variance."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_grid3 = Table([[c1, c2], [c3, c4]], colWidths=[360, 360])
    t_grid3.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    slides_content.append(t_grid3)
    slides_content.append(PageBreak())

    # Slide 4: 14 Knowledge Docs
    slides_content.append(Paragraph("Slide 4: Knowledge Base Integration (14 Shared Documents)", s_title))
    slides_content.append(Paragraph("MAPPING SHARED FILES TO SYSTEM LAYERS", s_sub))
    c1 = make_slide_card("1. RAG & System Prompt", [
        "01 - Agent Instructions: Evidence tagging ([Verified]/[Probable]) -> System Prompt.",
        "01 - Company Profile: Grounded facts (Pune hub, 10 staff) -> Vector DB.",
        "02 - Services & 03 - Capabilities: 8 service lines & CWCT standards -> RAG retrieval."
    ], width=350)
    c2 = make_slide_card("2. Web Research & Pydantic Brief", [
        "02 - Research Criteria: 8 research categories & target roles -> Scraper blueprint.",
        "04 - Research Output Template: 11-section layout -> Enforced Pydantic schema.",
        "03 - Strategy & 04 - Positioning: Value props & objections -> Brief hypotheses."
    ], width=350)
    c3 = make_slide_card("3. Scoring & Proposals", [
        "05 - ICP & Rubric: Revenue bands, geographic priority -> Pure Python scoring.",
        "08 - Proposal Templates: 3 commercial engagement models -> Next Action."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    c4 = make_slide_card("4. Multi-Touch Outreach", [
        "02 & 03 - LinkedIn Connection & Pitch: Role-specific connection & pitch drafts.",
        "04 & 05 - Email & Follow Up: 3-step cold email cadences & 4-touch follow-ups."
    ], width=350)
    t_grid4 = Table([[c1, c2], [c3, c4]], colWidths=[360, 360])
    t_grid4.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    slides_content.append(t_grid4)
    slides_content.append(PageBreak())

    # Slide 5: Codebase Architecture
    slides_content.append(Paragraph("Slide 5: Full Codebase Architecture & File Structure", s_title))
    slides_content.append(Paragraph("DIRECTORY BREAKDOWN & COMPONENT FUNCTION", s_sub))
    c1 = make_slide_card("Core Backend (`prospect-intelligence/`)", [
        "main.py: FastAPI REST endpoints, async task queue, worker loop.",
        "models.py: Pydantic schemas (Intake, ResearchBrief, ScoreBreakdown, CRM).",
        "config.py: Environment variables, API keys, threshold settings."
    ], width=230)
    c2 = make_slide_card("Intelligence Engines", [
        "researcher.py: Async web scraper, BeautifulSoup parser, URL tagging.",
        "rag.py: SentenceTransformers embeddings, vector search, citations.",
        "scoring/engine.py & rubric.py: Pure Python 100-point evaluator."
    ], width=230, bg=BLUE_LIGHT, border=BORDER_BLUE)
    c3 = make_slide_card("Outreach, CRM & Storage", [
        "outreach.py: Role-based email & LinkedIn generator.",
        "crm.py & export_db_to_excel.py: HubSpot JSON payload & Excel exporter.",
        "database.py: SQLite persistence for runs, briefs, and scores."
    ], width=230)
    c4 = make_slide_card("UI & Test Suite (`ui/` & `tests/`)", [
        "ui/: FastAPI Jinja2 templates, manifest.json, service-worker.js (PWA).",
        "static-demo/: Standalone offline interactive HTML dashboard.",
        "tests/: Unit & integration test suite (anti-fabrication, scoring, CRM adapter)."
    ], width=710)
    t_row5_1 = Table([[c1, c2, c3]], colWidths=[240, 240, 240])
    t_row5_2 = Table([[c4]], colWidths=[720])
    t_row5_1.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row5_1)
    slides_content.append(Spacer(1, 6))
    slides_content.append(t_row5_2)
    slides_content.append(PageBreak())

    # Slide 6: Scoring Engine
    slides_content.append(Paragraph("Slide 6: Deterministic 100-Point Lead Scoring Engine", s_title))
    slides_content.append(Paragraph("OBJECTIVE QUALIFICATION & ICP FACTORS", s_sub))
    c1 = make_slide_card("10 Weighted ICP Factors (100 Pts Total)", [
        "1. Trade Fit (20 pts): Façade specialist = 20, Roofing = 16, Main contractor = 10.",
        "2. Tender Volume (15 pts): >=3 tenders = 15, 1-2 projects = 10, None = 0.",
        "3. Geography (10 pts): UK = 10, US/Canada = 8, Europe/ANZ = 4, Other = 0.",
        "4. Company Size (10 pts): Tier 1 (£20M+) = 10, Tier 2 = 8, Tier 3 = 5.",
        "5. Estimating Need (10 pts): Tight deadlines/overflow = 10, Regular = 7.",
        "6. Drafting/BIM Need (10 pts): BIM L2 / shop drawing demand = 10, CAD = 7.",
        "7. Hiring Trigger (10 pts): Recruiting Estimators/QS = 10, Expansion = 4.",
        "8. Decision-Maker Access (5 pts): Pre-Con Director = 5, MD/Owner = 4.",
        "9. Outsourcing Readiness (5 pts): Uses technical subconsultants = 5.",
        "10. Commercial Fit (5 pts): Prompt payment = 5, Standard = 3, High risk = 0."
    ], width=450)
    c2 = make_slide_card("Priority Bands & Pure Code", [
        "HIGH PRIORITY (>= 70 Pts): Founder outreach & pilot takeoff pitch.",
        "MEDIUM PRIORITY (45–69 Pts): Standard email & LinkedIn connection.",
        "LOW PRIORITY (< 45 Pts): Nurture sequence or disqualify.",
        "------------------------------------",
        "Pure Python: Zero math hallucination; 100% audit trail and repeatability."
    ], width=250, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_row6 = Table([[c1, c2]], colWidths=[460, 260])
    t_row6.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row6)
    slides_content.append(PageBreak())

    # Slide 7: Grounded RAG
    slides_content.append(Paragraph("Slide 7: Grounded RAG & Anti-Fabrication Engine", s_title))
    slides_content.append(Paragraph("TWO-PILLAR RETRIEVAL & EVIDENCE STANDARDS", s_sub))
    c1 = make_slide_card("Internal RAG Architecture", [
        "Ingests 14 Coextend knowledge base PDFs into vector embeddings.",
        "Heading-aware chunking maintains section & document context.",
        "Top-k semantic retrieval injects exact capability snippets into LLM prompts with source metadata."
    ], width=350)
    c2 = make_slide_card("External Research & Tagging", [
        "Crawls company site, leadership, and public tender announcements.",
        "Tags findings with confidence tiers: [Verified] (direct URL), [Probable] (indirect), [Unverified].",
        "Every claim in brief includes clickable source citation."
    ], width=350)
    c3 = make_slide_card("Strict Anti-Fabrication Constraints", [
        "System prompt explicitly forbids guessing missing data.",
        "If data point cannot be verified, brief outputs 'No evidence found'.",
        "Eliminates false claims on sales calls and protects commercial reputation."
    ], width=710, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_row7_1 = Table([[c1, c2]], colWidths=[360, 360])
    t_row7_2 = Table([[c3]], colWidths=[720])
    t_row7_1.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row7_1)
    slides_content.append(Spacer(1, 6))
    slides_content.append(t_row7_2)
    slides_content.append(PageBreak())

    # Slide 8: Tech Stack & Resilience
    slides_content.append(Paragraph("Slide 8: Technology Stack & Production Engineering", s_title))
    slides_content.append(Paragraph("FASTAPI, PYDANTIC V2 & RESILIENCE", s_sub))
    c1 = make_slide_card("Production Stack Breakdown", [
        "Backend: Python 3.14 + FastAPI (Async REST API).",
        "Validation: Pydantic v2 (Strict typing, regex URL checks).",
        "Vector Engine: ChromaDB / FAISS + SentenceTransformers.",
        "Document Engine: ReportLab 5.0 (PDF) + python-pptx.",
        "Persistence: SQLite + JSON columns + Excel exporter."
    ], width=350)
    c2 = make_slide_card("Resilience & Rate Limit Handling", [
        "Async Scraper: Handles HTTP timeouts with exponential backoff.",
        "Cooldown: Enforces 24-hr domain scraping cooldown.",
        "Graceful Fallback: Scraper failure falls back to RAG mode.",
        "Structured Logging: All pipeline steps log detailed tracebacks."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_row8 = Table([[c1, c2]], colWidths=[360, 360])
    t_row8.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row8)
    slides_content.append(PageBreak())

    # Slide 9: Testing & Guardrails
    slides_content.append(Paragraph("Slide 9: Testing Suite, QA & Safety Guardrails", s_title))
    slides_content.append(Paragraph("SYSTEM VERIFICATION & COMPLIANCE RULES", s_sub))
    c1 = make_slide_card("Comprehensive Test Suite Coverage", [
        "test_anti_fabrication.py: Validates zero-guess enforcement.",
        "test_scoring.py: Verifies scoring across High/Med/Low leads.",
        "test_crm_adapter.py: Ensures HubSpot JSON payload validity.",
        "test_failure_injection.py: Tests network timeout resilience.",
        "test_e2e_prospects.py: End-to-end integration test suite."
    ], width=350)
    c2 = make_slide_card("Safety & Compliance Guardrails", [
        "1. No Automated LinkedIn Actions: Scraping & auto-sending strictly banned.",
        "2. Human-in-the-Loop: Outreach remains 'draft' for review.",
        "3. CRM Sandbox: Staged locally to protect live CRM data.",
        "4. Strict Grounding: Service claims restricted to ingested files."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_row9 = Table([[c1, c2]], colWidths=[360, 360])
    t_row9.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row9)
    slides_content.append(PageBreak())

    # Slide 10: Interview Q&A 1
    slides_content.append(Paragraph("Slide 10: Key Technical Interview Questions & Answers (1/2)", s_title))
    slides_content.append(Paragraph("DEFENDING ARCHITECTURAL DECISIONS", s_sub))
    c1 = make_slide_card("Q1: Why separate RAG from Web Research?", [
        "RAG holds Coextend internal IP; Web research holds external prospect data.",
        "Mixing them leads to LLM confusing Coextend services with prospect capabilities.",
        "Guarantees 100% accurate service matching."
    ], width=350)
    c2 = make_slide_card("Q2: Why Python for Lead Scoring, not LLM?", [
        "LLMs yield erratic, probabilistic 'vibes' scores.",
        "Python code guarantees 100% mathematical consistency, auditability, and zero API cost."
    ], width=350)
    c3 = make_slide_card("Q3: How do you prevent AI Hallucinations?", [
        "System prompt anti-guess policy ('No evidence found').",
        "Grounded RAG with exact document citations.",
        "Pydantic schema validation for all LLM outputs."
    ], width=350)
    c4 = make_slide_card("Q4: How does CRM Export work?", [
        "crm.py maps research brief to HubSpot Company & Contact schema.",
        "Includes domain deduplication and exports JSON/CSV staged payloads."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_grid10 = Table([[c1, c2], [c3, c4]], colWidths=[360, 360])
    t_grid10.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    slides_content.append(t_grid10)
    slides_content.append(PageBreak())

    # Slide 11: Interview Q&A 2
    slides_content.append(Paragraph("Slide 11: Key Technical Interview Questions & Answers (2/2)", s_title))
    slides_content.append(Paragraph("DEFENDING ENGINEERING TRADE-OFFS", s_sub))
    c1 = make_slide_card("Q5: How do you handle anti-scraping / rate limits?", [
        "Browser headers, rate-limiting delays, timeout bounds, and 24-hr domain cooldowns.",
        "Scraper failure falls back gracefully to basic domain analysis without crashing."
    ], width=350)
    c2 = make_slide_card("Q6: Why FastAPI and Pydantic v2?", [
        "FastAPI provides native async support for non-blocking I/O.",
        "Pydantic v2 provides C-compiled fast validation and strict schema enforcement."
    ], width=350)
    c3 = make_slide_card("Q7: Why strictly avoid LinkedIn automation?", [
        "LinkedIn aggressively detects automated actions, risking domain & account bans.",
        "Keeping outreach human-in-the-loop ensures 100% safety and high conversion quality."
    ], width=350)
    c4 = make_slide_card("Q8: What would you build in Phase 2?", [
        "Real-time webhook sync with HubSpot/Salesforce.",
        "Automated tender portal monitoring (Tenders Direct, Contracts Finder).",
        "Multi-agent parallel web research for enterprise accounts."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_grid11 = Table([[c1, c2], [c3, c4]], colWidths=[360, 360])
    t_grid11.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
    slides_content.append(t_grid11)
    slides_content.append(PageBreak())

    # Slide 12: Roadmap & Impact
    slides_content.append(Paragraph("Slide 12: 5-Day Delivery Roadmap & Final Business Impact", s_title))
    slides_content.append(Paragraph("MILESTONE EXECUTION & ROI", s_sub))
    c1 = make_slide_card("5-Day Milestone Delivery Schedule", [
        "Day 1: Architecture blueprint, repository skeleton, Pydantic schemas, FastAPI /health.",
        "Day 2: PDF RAG vector ingestion + web research engine tested on initial prospects.",
        "Day 3: Deterministic lead scoring engine + brief generator + CRM export adapter.",
        "Day 4: Outreach generator + UI dashboard + resilience logging & error handling.",
        "Day 5: 5-prospect evaluation suite, unit tests, master documentation & candidate presentation."
    ], width=350)
    c2 = make_slide_card("Business Impact & Value Delivered", [
        "Time Saved: 90%+ reduction in pre-sales research time (45 mins -> 3 mins per lead).",
        "Scale: Enables founder to evaluate 500+ prospects/month easily.",
        "Accuracy: 100% grounded technical citations with 0% capability hallucination.",
        "Pipeline Quality: Objective 100-point scoring focuses sales team on High-Priority leads.",
        "Status: System architecture, verification docs & candidate presentation 100% complete."
    ], width=350, bg=BLUE_LIGHT, border=BORDER_BLUE)
    t_row12 = Table([[c1, c2]], colWidths=[360, 360])
    t_row12.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    slides_content.append(t_row12)

    doc.build(slides_content)
    print(f"Successfully generated Landscape Presentation PDF at: {output_path}")

if __name__ == "__main__":
    out_pdf = r"C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI\Coextend_AI_Project_Presentation.pdf"
    generate_presentation_pdf(out_pdf)
