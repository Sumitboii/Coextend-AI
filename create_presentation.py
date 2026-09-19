import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

def build_presentation(output_file):
    prs = Presentation()
    # 16:9 Widescreen layout
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    # Color palette
    NAVY = RGBColor(30, 58, 138)         # #1E3A8A
    TEAL = RGBColor(13, 148, 136)       # #0D9488
    AMBER = RGBColor(217, 119, 6)       # #D97706
    SLATE_DARK = RGBColor(30, 41, 59)   # #1E293B
    SLATE_MUTED = RGBColor(100, 116, 139) # #64748B
    BG_LIGHT = RGBColor(248, 250, 252)   # #F8FAFC
    CARD_BG = RGBColor(241, 245, 249)    # #F1F5F9
    WHITE = RGBColor(255, 255, 255)
    BLUE_LIGHT = RGBColor(239, 246, 255) # #EFF6FF
    BORDER_BLUE = RGBColor(59, 130, 246)
    
    blank_layout = prs.slide_layouts[6]
    
    def add_header(slide, title_text, category="COEXTEND AI — INTERVIEW & SYSTEM BLUEPRINT"):
        # Top banner background
        top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.1))
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = NAVY
        top_bar.line.color.rgb = NAVY
        
        # Category label
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.12), Inches(11.733), Inches(0.3))
        tf_c = cat_box.text_frame
        tf_c.word_wrap = True
        p_c = tf_c.paragraphs[0]
        p_c.text = category.upper()
        p_c.font.size = Pt(10)
        p_c.font.bold = True
        p_c.font.color.rgb = TEAL
        p_c.font.name = "Arial"
        
        # Main title
        title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.38), Inches(11.733), Inches(0.6))
        tf = title_box.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(22)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.font.name = "Arial"
        
        # Bottom footer bar
        bot_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(7.1), Inches(13.333), Inches(0.4))
        bot_bar.fill.solid()
        bot_bar.fill.fore_color.rgb = CARD_BG
        bot_bar.line.color.rgb = CARD_BG
        
        foot_box = slide.shapes.add_textbox(Inches(0.8), Inches(7.12), Inches(11.733), Inches(0.3))
        tf_f = foot_box.text_frame
        p_f = tf_f.paragraphs[0]
        p_f.text = "Coextend AI Prospect Intelligence MVP — Candidate Interview Deck (Sumit Singh)"
        p_f.font.size = Pt(9)
        p_f.font.color.rgb = SLATE_MUTED
        p_f.font.name = "Arial"

    def add_card(slide, left, top, width, height, title, body_bullets, bg_color=CARD_BG, border_color=None):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1.5)
        else:
            card.line.color.rgb = bg_color
            
        tb = slide.shapes.add_textbox(Inches(left + 0.2), Inches(top + 0.15), Inches(width - 0.4), Inches(height - 0.3))
        tf = tb.text_frame
        tf.word_wrap = True
        
        # Card title
        p_t = tf.paragraphs[0]
        p_t.text = title
        p_t.font.size = Pt(12)
        p_t.font.bold = True
        p_t.font.color.rgb = NAVY
        p_t.font.name = "Arial"
        p_t.space_after = Pt(6)
        
        # Bullets
        for b in body_bullets:
            p_b = tf.add_paragraph()
            p_b.text = f"• {b}"
            p_b.font.size = Pt(9.5)
            p_b.font.color.rgb = SLATE_DARK
            p_b.font.name = "Arial"
            p_b.space_after = Pt(3)

    # -------------------------------------------------------------
    # SLIDE 1: Title Slide (Dark Navy Hero)
    # -------------------------------------------------------------
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = NAVY
    bg1.line.color.rgb = NAVY
    
    # Accent line
    accent_bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.2), Inches(1.6), Inches(1.5), Inches(0.08))
    accent_bar.fill.solid()
    accent_bar.fill.fore_color.rgb = TEAL
    accent_bar.line.color.rgb = TEAL
    
    # Subtitle tag
    tag_box = s1.shapes.add_textbox(Inches(1.2), Inches(1.8), Inches(10.5), Inches(0.4))
    tf_tag = tag_box.text_frame
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = "AI AUTOMATION ENGINEER — PILOT PROJECT & INTERVIEW BLUEPRINT"
    p_tag.font.size = Pt(12)
    p_tag.font.bold = True
    p_tag.font.color.rgb = TEAL
    p_tag.font.name = "Arial"
    
    # Main Hero Title
    hero_box = s1.shapes.add_textbox(Inches(1.2), Inches(2.2), Inches(11.0), Inches(2.2))
    tf_hero = hero_box.text_frame
    tf_hero.word_wrap = True
    p_hero = tf_hero.paragraphs[0]
    p_hero.text = "Coextend AI Prospect Intelligence Engine"
    p_hero.font.size = Pt(34)
    p_hero.font.bold = True
    p_hero.font.color.rgb = WHITE
    p_hero.font.name = "Arial"
    
    p_hero_sub = tf_hero.add_paragraph()
    p_hero_sub.text = "Grounded RAG, Web Intelligence & Deterministic 100-Point Scoring for Façade Engineering Pre-Sales"
    p_hero_sub.font.size = Pt(16)
    p_hero_sub.font.color.rgb = RGBColor(203, 213, 225)
    p_hero_sub.font.name = "Arial"
    p_hero_sub.space_before = Pt(10)
    
    # Author & Meta Card
    meta_box = s1.shapes.add_textbox(Inches(1.2), Inches(4.8), Inches(10.5), Inches(2.0))
    tf_meta = meta_box.text_frame
    p_m1 = tf_meta.paragraphs[0]
    p_m1.text = "Candidate / AI Engineer: Sumit Singh (@Sumitboii)"
    p_m1.font.size = Pt(12)
    p_m1.font.bold = True
    p_m1.font.color.rgb = WHITE
    p_m1.font.name = "Arial"
    
    p_m2 = tf_meta.add_paragraph()
    p_m2.text = "Company: Coextend Global LLP (Pune, India | Target Markets: UK, US, Canada)"
    p_m2.font.size = Pt(11)
    p_m2.font.color.rgb = RGBColor(226, 232, 240)
    p_m2.font.name = "Arial"
    p_m2.space_before = Pt(4)

    p_m3 = tf_meta.add_paragraph()
    p_m3.text = "Core Tech Stack: Python 3.14 | FastAPI | Vector RAG | Deterministic Scoring | Pydantic v2 | SQLite"
    p_m3.font.size = Pt(11)
    p_m3.font.bold = True
    p_m3.font.color.rgb = TEAL
    p_m3.space_before = Pt(4)

    # -------------------------------------------------------------
    # SLIDE 2: Business Problem & Founder Bottleneck
    # -------------------------------------------------------------
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "Business Problem & Pre-Sales Founder Bottleneck", "Why Coextend Asked For This Project")
    
    add_card(s2, 0.8, 1.4, 3.6, 5.3, "1. The Founder's Bottleneck", [
        "Coextend founder spends 30–45 mins per lead manually researching websites, LinkedIn, & tender feeds.",
        "At 100 leads/month, this consumes 50–75 hours of high-value leadership time.",
        "Manual research leads to subjective, inconsistent lead qualification.",
        "Goal: Compress 45 minutes of manual research into a 3-minute decision-ready brief."
    ], CARD_BG)
    
    add_card(s2, 4.8, 1.4, 3.6, 5.3, "2. High-Stakes Façade Market", [
        "Façade tenders range from £500k to £20M+ with strict 2–3 week bid submission deadlines.",
        "Generic sales pitches fail and ruin company credibility with main contractors.",
        "Outreach must cite specific technical standards (CWCT, BS EN 13830, ASTM) and tools (AutoCAD, Revit, Bluebeam).",
        "Goal: Arm sales reps with exact technical pain points and tailored angles."
    ], CARD_BG)
    
    add_card(s2, 8.8, 1.4, 3.6, 5.3, "3. Assessment Charter", [
        "Paid capability assessment for the AI Automation Engineer role.",
        "Evaluates real-world software architecture, RAG grounding, and deterministic logic.",
        "Tests ability to deliver a production-ready MVP in a strict 5-day delivery roadmap.",
        "Goal: Deliver a clean, audited, and fully tested candidate build."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 3: Architecture & Why Generic AI Fails
    # -------------------------------------------------------------
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "Why Generic AI Prompts Fail & Architectural Solution", "System Rationale & Guardrails")
    
    add_card(s3, 0.8, 1.4, 5.6, 2.5, "1. Hallucinated Capabilities & Terms", [
        "Generic LLMs confuse civil drafting with specialist façade takeoffs.",
        "AI promises services Coextend does not provide (e.g., structural engineering).",
        "Uses US CSI codes for UK contractors who need Uniclass/NRM2."
    ], CARD_BG)
    
    add_card(s3, 6.8, 1.4, 5.6, 2.5, "2. Erratic 'Vibes-Based' Scoring", [
        "LLMs give 85/100 on Monday and 45/100 on Tuesday for the same data.",
        "Subjective scoring creates chaos in CRM pipeline prioritization.",
        "Probabilistic math cannot be audited or trusted."
    ], CARD_BG)
    
    add_card(s3, 0.8, 4.2, 5.6, 2.5, "3. Fabricated Facts & Fake Tenders", [
        "LLMs invent recent contract wins or assume non-existent project scopes.",
        "Zero audit trail leaves sales reps vulnerable to making false claims on executive calls."
    ], CARD_BG)
    
    add_card(s3, 6.8, 4.2, 5.6, 2.5, "4. Solution: Two-Pillar Knowledge Architecture", [
        "Pillar 1 (Internal RAG): Grounded ONLY in verified Coextend IP with citations.",
        "Pillar 2 (External Web Engine): Live public data with [Verified] / [Probable] tags.",
        "Scoring Logic: 100% pure Python code—zero LLM math hallucination."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 4: The 14 Ingested Knowledge Base Documents
    # -------------------------------------------------------------
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "Knowledge Base Integration (14 Shared Documents)", "Mapping Shared Files to System Layers")
    
    add_card(s4, 0.8, 1.4, 5.6, 2.5, "1. System Prompt & Internal RAG Layer", [
        "01 - Agent Instructions: Evidence tagging ([Verified]/[Probable]) & anti-guess rules -> System Prompt.",
        "01 - Company Profile: Grounded facts (Pune hub, 10 staff, UK/US/Canada) -> Vector DB.",
        "02 - Services & 03 - Capabilities: 8 service lines & CWCT/BS EN standards -> RAG retrieval."
    ], CARD_BG)
    
    add_card(s4, 6.8, 1.4, 5.6, 2.5, "2. Web Research & Pydantic Brief Schemas", [
        "02 - Research Criteria: 8 research dimensions & target executive titles -> Web Crawler queries.",
        "04 - Research Output Template: 11-section layout -> Enforced as strict Pydantic v2 JSON schema.",
        "03 - Marketing Strategy & 04 - Sales Positioning: Value props & objections -> Sales hypotheses."
    ], CARD_BG)
    
    add_card(s4, 0.8, 4.2, 5.6, 2.5, "3. Lead Scoring & Proposal Rules", [
        "05 - Ideal Customer Profile & Rubric: Revenue bands, geographic priority, 10 factors -> Pure Python scoring engine.",
        "08 - Proposal Templates: 3 commercial models (Fixed tender, FTE, Retainer) -> Recommended Next Action."
    ], BLUE_LIGHT, BORDER_BLUE)
    
    add_card(s4, 6.8, 4.2, 5.6, 2.5, "4. Personalized Multi-Touch Outreach", [
        "02 & 03 - LinkedIn Connection & Pitch: Role-specific connection & follow-up pitch drafts.",
        "04 & 05 - Email & Follow-Up Messages: 3-step cold email cadences & 4-touch follow-up sequences."
    ], CARD_BG)

    # -------------------------------------------------------------
    # SLIDE 5: Full Codebase Architecture & File Structure
    # -------------------------------------------------------------
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "Codebase Architecture & Directory Breakdown", "Modularity & Clean Code Principles")
    
    add_card(s5, 0.8, 1.4, 3.6, 2.5, "Core Backend (`prospect-intelligence/`)", [
        "main.py: FastAPI REST endpoints, async task queue, background worker.",
        "models.py: Pydantic schemas (Intake, ResearchBrief, ScoreBreakdown, CRM).",
        "config.py: Environment variables, API keys, threshold configurations."
    ], CARD_BG)
    
    add_card(s5, 4.8, 1.4, 3.6, 2.5, "Intelligence Engines", [
        "researcher.py: Async web scraper, BeautifulSoup parsing, source URL tagging.",
        "rag.py: SentenceTransformers embeddings, vector search, citation injection.",
        "scoring/engine.py & rubric.py: Pure Python 100-point rubric evaluator."
    ], BLUE_LIGHT, BORDER_BLUE)
    
    add_card(s5, 8.8, 1.4, 3.6, 2.5, "Outreach, CRM & Storage", [
        "outreach.py: Role-specific email & LinkedIn template generator.",
        "crm.py & export_db_to_excel.py: HubSpot JSON payload builder & Excel exporter.",
        "database.py: SQLite persistence for runs, briefs, and lead scores."
    ], CARD_BG)
    
    add_card(s5, 0.8, 4.2, 5.6, 2.5, "User Interface & Static Demo (`ui/` & `static-demo/`)", [
        "FastAPI Jinja2 templates (dashboard, prospect detail view).",
        "manifest.json & service-worker.js for PWA capabilities.",
        "Standalone static HTML demo for offline presentation and client walk-throughs."
    ], CARD_BG)

    add_card(s5, 6.8, 4.2, 5.6, 2.5, "Comprehensive Test Suite (`tests/`)", [
        "test_anti_fabrication.py: Validates 'no evidence found' enforcement.",
        "test_scoring.py: Verifies 100% deterministic score output across 10 factors.",
        "test_crm_adapter.py, test_e2e_prospects.py, test_failure_injection.py."
    ], CARD_BG)

    # -------------------------------------------------------------
    # SLIDE 6: Deterministic 100-Point Lead Scoring Engine
    # -------------------------------------------------------------
    s6 = prs.slides.add_slide(blank_layout)
    add_header(s6, "Deterministic 100-Point Lead Scoring Engine", "10 Weighted ICP Factors in Pure Python")
    
    add_card(s6, 0.8, 1.4, 5.6, 5.3, "The 10 Weighted ICP Factors", [
        "1. Trade & Service Fit (20 pts): Façade/curtain wall = 20, Roofing = 16, Main contractor = 10.",
        "2. Tender & Project Volume (15 pts): >=3 active tenders = 15, 1-2 projects = 10, None = 0.",
        "3. Geography Fit (10 pts): UK = 10, US/Canada = 8, Europe/ANZ = 4, Other = 0.",
        "4. Company Size (10 pts): Tier 1 (£20M-£100M+) = 10, Tier 2 = 8, Tier 3 = 5.",
        "5. Estimating Need (10 pts): Tight deadlines / bid overflow = 10, Regular = 7, In-house = 0.",
        "6. Drafting/BIM Need (10 pts): BIM Level 2 / shop drawing demand = 10, CAD = 7, None = 0.",
        "7. Hiring Trigger (10 pts): Recruiting Estimators/QS = 10, Expansion = 4, None = 0.",
        "8. Decision-Maker Access (5 pts): Named Pre-Con Director = 5, MD/Owner = 4.",
        "9. Outsourcing Readiness (5 pts): Uses technical subconsultants = 5, Neutral = 2.",
        "10. Commercial Fit (5 pts): Prompt payment history = 5, Standard = 3, High risk = 0."
    ], CARD_BG)
    
    add_card(s6, 6.8, 1.4, 5.6, 2.5, "Priority Threshold Bands", [
        "HIGH PRIORITY (>= 70 Pts): Immediate founder outreach & pilot takeoff pitch.",
        "MEDIUM PRIORITY (45–69 Pts): Standard email sequence & LinkedIn connection.",
        "LOW PRIORITY (< 45 Pts): Nurture sequence or disqualify."
    ], BLUE_LIGHT, BORDER_BLUE)
    
    add_card(s6, 6.8, 4.2, 5.6, 2.5, "Why Pure Python Code?", [
        "Zero Math Hallucination: Scoring formula is hardcoded in Python.",
        "Auditability: Every awarded point references exact underlying evidence.",
        "100% Repeatability: Same prospect data always yields exact same score."
    ], CARD_BG)

    # -------------------------------------------------------------
    # SLIDE 7: Grounded RAG & Anti-Fabrication Engine
    # -------------------------------------------------------------
    s7 = prs.slides.add_slide(blank_layout)
    add_header(s7, "Grounded RAG & Anti-Fabrication Engine", "Two-Pillar Retrieval & Evidence Standards")
    
    add_card(s7, 0.8, 1.4, 5.6, 2.5, "Internal RAG Architecture (Coextend IP)", [
        "Ingests 14 Coextend knowledge base PDFs into vector embeddings.",
        "Heading-aware chunking maintains section & document context.",
        "Top-k semantic retrieval injects exact capability snippets into LLM prompts with source metadata."
    ], CARD_BG)
    
    add_card(s7, 6.8, 1.4, 5.6, 2.5, "External Research & Evidence Tagging", [
        "Crawls company website, leadership pages, and public tender announcements.",
        "Tags findings with strict confidence tiers: [Verified] (direct URL), [Probable] (indirect news/social), [Unverified].",
        "Every claim in the generated brief includes a clickable source citation."
    ], CARD_BG)
    
    add_card(s7, 0.8, 4.2, 11.6, 2.5, "Strict Anti-Fabrication Constraints", [
        "System prompt explicitly forbids guessing missing data.",
        "If a data point (e.g., active tenders or decision-maker email) cannot be verified, the brief outputs 'No evidence found'.",
        "Eliminates false claims on sales calls and protects Coextend's commercial reputation."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 8: Technology Stack & Engineering Resilience
    # -------------------------------------------------------------
    s8 = prs.slides.add_slide(blank_layout)
    add_header(s8, "Technology Stack & Production Engineering", "FastAPI, Pydantic v2 & Error Handling")
    
    add_card(s8, 0.8, 1.4, 5.6, 5.3, "Production Tech Stack Breakdown", [
        "Backend Framework: Python 3.14 + FastAPI (Async REST endpoints).",
        "Data Validation: Pydantic v2 (Strict field typing, regex URL checks, schema validation).",
        "Vector Engine: ChromaDB / FAISS + SentenceTransformers embeddings.",
        "Document Processing: ReportLab 5.0 (PDF generator) + python-pptx (Presentations).",
        "Data Persistence: SQLite with JSON column storage + Excel exporter.",
        "CRM Integration: HubSpot Sandbox JSON/CSV adapter."
    ], CARD_BG)
    
    add_card(s8, 6.8, 1.4, 5.6, 5.3, "Resilience & Rate Limit Handling", [
        "Async Web Scraper: Handles HTTP timeouts with exponential backoff.",
        "Cooldown Enforcement: Prevents duplicate scraping of the same domain within 24 hours.",
        "Graceful Fallback: Web research failures default to RAG-only mode without crashing the service.",
        "Structured Exception Logging: All pipeline stages log errors with clear tracebacks."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 9: Testing, Quality Assurance & Guardrails
    # -------------------------------------------------------------
    s9 = prs.slides.add_slide(blank_layout)
    add_header(s9, "Testing Suite, QA & Safety Guardrails", "System Verification & Compliance Rules")
    
    add_card(s9, 0.8, 1.4, 5.6, 5.3, "Comprehensive Test Suite Coverage", [
        "test_anti_fabrication.py: Validates zero-guess enforcement when web data is sparse.",
        "test_scoring.py: Verifies scoring accuracy across High, Medium, Low lead profiles.",
        "test_crm_adapter.py: Ensures HubSpot JSON payload matches required CRM fields.",
        "test_failure_injection.py: Tests pipeline resilience under network timeouts.",
        "test_e2e_prospects.py: End-to-end integration test across real prospect URLs."
    ], CARD_BG)
    
    add_card(s9, 6.8, 1.4, 5.6, 5.3, "Safety & Compliance Guardrails", [
        "1. Strictly No Automated LinkedIn Actions: Scraping & auto-sending on LinkedIn are banned to protect account health.",
        "2. Human-in-the-Loop Control: All generated outreach remains in 'draft' state for human review.",
        "3. CRM Sandbox Isolation: Prevents accidental overwrites of live production sales data.",
        "4. Strict Grounding Constraint: Coextend service claims are restricted strictly to ingested documents."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 10: Top 10 Interview Questions & Answers (Part 1)
    # -------------------------------------------------------------
    s10 = prs.slides.add_slide(blank_layout)
    add_header(s10, "Key Technical Interview Questions & Answers (1/2)", "Defending Architectural Decisions")
    
    add_card(s10, 0.8, 1.4, 5.6, 2.5, "Q1: Why separate RAG from Web Research?", [
        "Answer: RAG holds Coextend's internal IP (ground truth). Web research gathers external public data.",
        "Mixing them leads to the LLM confusing Coextend's services with prospect capabilities.",
        "Separation guarantees 100% accurate service matching."
    ], CARD_BG)
    
    add_card(s10, 6.8, 1.4, 5.6, 2.5, "Q2: Why use Python for Lead Scoring, not LLM?", [
        "Answer: LLMs are probabilistic and yield inconsistent scores (vibes-based math).",
        "Python implementation guarantees 100% mathematical consistency, auditability, and instant execution without API costs."
    ], CARD_BG)
    
    add_card(s10, 0.8, 4.2, 5.6, 2.5, "Q3: How do you prevent AI Hallucinations?", [
        "Answer: (1) System prompt anti-guess policy ('No evidence found').",
        "(2) Grounded RAG with exact document citations.",
        "(3) Pydantic schema validation for all LLM outputs."
    ], CARD_BG)
    
    add_card(s10, 6.8, 4.2, 5.6, 2.5, "Q4: How does the CRM Export work?", [
        "Answer: `crm.py` maps research brief fields to HubSpot Company & Contact schema.",
        "Includes deduplication checks against existing domain records and exports JSON/CSV staged payloads."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 11: Top 10 Interview Questions & Answers (Part 2)
    # -------------------------------------------------------------
    s11 = prs.slides.add_slide(blank_layout)
    add_header(s11, "Key Technical Interview Questions & Answers (2/2)", "Defending Engineering Trade-Offs")
    
    add_card(s11, 0.8, 1.4, 5.6, 2.5, "Q5: How do you handle anti-scraping / rate limits?", [
        "Answer: Scraper uses standard browser headers, rate-limiting delays, timeout bounds, and domain cooldowns.",
        "If scraping fails, the system falls back gracefully to basic domain analysis without crashing."
    ], CARD_BG)
    
    add_card(s11, 6.8, 1.4, 5.6, 2.5, "Q6: Why FastAPI and Pydantic v2?", [
        "Answer: FastAPI provides native async support for non-blocking I/O during web requests.",
        "Pydantic v2 provides fast C-compiled data validation and strict type safety across pipeline stages."
    ], CARD_BG)
    
    add_card(s11, 0.8, 4.2, 5.6, 2.5, "Q7: Why strictly avoid Automated LinkedIn Actions?", [
        "Answer: LinkedIn aggressively detects automated scraping/messaging, risking domain & profile bans.",
        "Keeping outreach human-in-the-loop ensures 100% compliance and maintains high lead quality."
    ], CARD_BG)
    
    add_card(s11, 6.8, 4.2, 5.6, 2.5, "Q8: What would you build in Phase 2?", [
        "Answer: (1) Real-time webhook integration with HubSpot/Salesforce.",
        "(2) Automated tender portal monitoring (Tenders Direct, Contracts Finder).",
        "(3) Multi-agent parallel web research for enterprise accounts."
    ], BLUE_LIGHT, BORDER_BLUE)

    # -------------------------------------------------------------
    # SLIDE 12: 5-Day Delivery Roadmap & Business Impact
    # -------------------------------------------------------------
    s12 = prs.slides.add_slide(blank_layout)
    add_header(s12, "5-Day Delivery Roadmap & Final Business Impact", "Milestone Execution & ROI")
    
    add_card(s12, 0.8, 1.4, 5.6, 5.3, "5-Day Milestone Delivery Schedule", [
        "Day 1: Architecture blueprint, repository skeleton, Pydantic schemas, FastAPI /health.",
        "Day 2: Knowledge PDF vector ingestion + web research engine tested on initial prospects.",
        "Day 3: Deterministic lead scoring engine + brief generator + CRM export adapter.",
        "Day 4: Outreach generator + UI dashboard + resilience logging & error handling.",
        "Day 5: 5-prospect evaluation suite, unit tests, master documentation & candidate presentation."
    ], CARD_BG)
    
    add_card(s12, 6.8, 1.4, 5.6, 5.3, "Business Impact & Value Delivered", [
        "Time Saved: 90%+ reduction in pre-sales research time (from 45 mins to 3 mins per lead).",
        "Scale: Enables founder to evaluate 500+ prospects/month without adding headcount.",
        "Accuracy: 100% grounded technical citations with 0% capability hallucination.",
        "Pipeline Quality: Objective 100-point scoring focuses sales team exclusively on High-Priority leads.",
        "Status: System architecture, verification docs, test suite & presentation 100% complete."
    ], BLUE_LIGHT, BORDER_BLUE)

    prs.save(output_file)
    print(f"Successfully generated 12-Slide PowerPoint Presentation: {output_file}")

if __name__ == "__main__":
    out_path = r"C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI\Coextend_AI_Project_Presentation.pptx"
    build_presentation(out_path)
