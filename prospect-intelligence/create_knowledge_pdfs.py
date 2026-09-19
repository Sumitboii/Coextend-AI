#!/usr/bin/env python3
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os

inch = 72  # 1 inch = 72 points

os.makedirs('data/knowledge_base', exist_ok=True)

def create_pdf(filename, title, content_lines):
    c = canvas.Canvas(filename, pagesize=letter)
    c.setTitle(title)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(0.5*inch, 10.5*inch, title)
    c.setFont('Helvetica', 10)
    y = 10*inch
    for line in content_lines:
        if y < 0.5*inch:
            c.showPage()
            c.setFont('Helvetica', 10)
            y = 10*inch
        c.drawString(0.5*inch, y, line)
        y -= 0.18*inch
    c.save()

# 1. Services
content = [
    'Coextend specializes in outsourcing technical services for construction.',
    'FACADE DESIGN AND ESTIMATING:',
    'We provide facade and cladding design services including detailed cost',
    'estimating and material take-offs. We specialize in curtain wall systems,',
    'storefront glazing, aluminum extrusions, and roofing assemblies.',
    '',
    'SHOP DRAWING PRODUCTION:',
    'We create high-quality shop drawings using Revit, AutoCAD, and Tekla.',
    'Accurate, buildable drawings for fabricators and contractors.',
    '',
    'BIM MODELING AND COORDINATION:',
    'Building Information Models for coordination, clash detection, and',
    'constructability. Experience spans facade, structural, and MEP.',
    '',
    'QUANTITY SURVEYING AND BOQ:',
    'We prepare bills of quantities, material schedules, and cost breakdowns',
    'for competitive bidding and project planning.',
    '',
    'CAD DRAFTING SERVICES:',
    'Technical drafting for construction documents across platforms.',
    '',
    'Team: 15+ years in construction documentation. We work with general',
    'contractors, specialty trades, and design firms on projects from 5M to 500M+.',
]
create_pdf('data/knowledge_base/01-services.pdf', 'Coextend Services', content)

# 2. Company Profile
content = [
    'COEXTEND: COMPANY OVERVIEW',
    '',
    'MISSION:',
    'Provide high-quality, cost-effective technical documentation and BIM',
    'services that accelerate project delivery and reduce project costs.',
    '',
    'Founded: 2012',
    'Headquarters: Virtual (Global team)',
    'Team Size: 25+ highly trained architects and engineers',
    '',
    'KEY STRENGTHS:',
    '- Deep expertise in facade, curtain wall, building envelope systems',
    '- Fast turnaround with 24-hour global coverage',
    '- Cost-effective pricing 40-60% below onshore rates',
    '- 99.2% first-pass approval rate on shop drawings',
    '- Strong relationships with Tier-1 contractors',
    '',
    'SERVICE DELIVERY:',
    '- Project-based engagement (one-off to full project management)',
    '- Retainer arrangements for ongoing capacity',
    '- Dedicated team models for long-term partnerships',
    '- Real-time collaboration via Slack, BIM360, SharePoint',
    '',
    'INDUSTRIES SERVED:',
    '- Commercial construction (office, retail, hospitality)',
    '- Specialty contractors (facade, glazing, roofing, steel)',
    '- Architectural firms',
    '- Engineering consultants',
]
create_pdf('data/knowledge_base/02-company-profile.pdf', 'Company Profile', content)

# 3. Capabilities
content = [
    'COEXTEND TECHNICAL CAPABILITIES',
    '',
    'SOFTWARE PLATFORMS:',
    '- Revit Architecture/Structure (native and coordination)',
    '- AutoCAD (2D production and detail design)',
    '- Tekla Structures (BIM structural modeling)',
    '- Navisworks (clash detection and 4D simulation)',
    '- Adobe Suite (visualization)',
    '- SketchUp (concept design and presentation)',
    '- SkyCiv (structural analysis and design)',
    '',
    'EXPERTISE AREAS:',
    'Building Facade Systems: Curtain wall, storefront, glazing, aluminum',
    'Roofing and Waterproofing: Membrane, sloped, flashing, coordination',
    'Structural Steel: Connection design, fabrication per AISC standards',
    'MEP Coordination: Full building systems integration',
    '',
    'PROJECT TYPES:',
    '- New construction (ground-up buildings)',
    '- Renovation and retrofit',
    '- Interior buildout and core-and-shell',
    '- Complex geometries and parametric design',
    '',
    'QUALITY STANDARDS:',
    '- AIA standards compliance',
    '- CSI/MasterFormat organization',
    '- Code compliance review',
    '- Constructability analysis',
    '- Revision management and issue tracking',
]
create_pdf('data/knowledge_base/03-capabilities.pdf', 'Technical Capabilities', content)

# 4. ICP
content = [
    'IDEAL CUSTOMER PROFILE (ICP)',
    '',
    'PRIMARY TARGET: SPECIALTY CONTRACTORS',
    '- Facade/curtain wall contractors (20M-500M revenue)',
    '- Glazing companies (regional to national)',
    '- Roofing contractors with commercial focus',
    '- Structural steel fabricators',
    '',
    'SECONDARY: GENERAL CONTRACTORS',
    '- Multi-trade contractors (50M+ annual revenue)',
    '- Regional and national builders',
    '- Build-to-suit developers',
    '',
    'TERTIARY: ARCHITECTURAL & ENGINEERING FIRMS',
    '- Mid-size firms (10M-100M revenue)',
    '- BIM-enabled practices',
    '- Design-build firms',
    '',
    'DECISION MAKERS:',
    '- Vice President of Operations',
    '- Project Manager',
    '- Technical Director / BIM Manager',
    '- Estimating Manager',
    '',
    'PAIN POINTS WE SOLVE:',
    '1. Overwhelmed with project workload (need temporary capacity)',
    '2. Estimating backlog (need quantity take-offs)',
    '3. Shop drawing delays (need fast, accurate drafting)',
    '4. BIM coordination (need skilled modelers)',
    '5. Staff retention challenges',
    '6. Quality control (need standardized drawings)',
    '',
    'ENGAGEMENT TRIGGERS:',
    '- Winning large projects',
    '- Seasonal volume spikes',
    '- Staff turnover',
    '- Expansion into new services',
    '- System upgrades or software migrations',
]
create_pdf('data/knowledge_base/04-icp.pdf', 'Ideal Customer Profile', content)

# 5. Outreach Templates
content = [
    'OUTREACH MESSAGE TEMPLATES',
    '',
    'OPENING ANGLE 1: CAPACITY/WORKLOAD',
    'Hi [Name], I noticed [Company] has been winning large projects lately.',
    'How are you managing the estimating and shop drawing workload?',
    'Have you considered outsourcing to maintain quality with volume increase?',
    '',
    'OPENING ANGLE 2: HIRING CHALLENGE',
    'I saw [Company] is hiring CAD drafters/BIM coordinators.',
    'Before you start a hiring process, have you explored outsourcing as',
    'a way to ramp capacity in 2 weeks instead of 2 months?',
    '',
    'OPENING ANGLE 3: PROJECT-SPECIFIC',
    'We work with several contractors on complex projects.',
    'I thought you might find value in our service.',
    'We have helped similar firms reduce estimating turnaround from',
    '3 weeks to 5 days. Worth a quick 15-minute conversation?',
    '',
    'KEY BENEFITS:',
    '- Save 40-60% on labor costs vs. hiring full-time',
    '- Scale up/down without fixed overhead',
    '- Get work done in 48 hours',
    '- Access to specialized expertise',
    '- Improve bid quality and accuracy',
    '',
    'PROOF POINTS:',
    '- 99.2% first-pass approval rate on shop drawings',
    '- 24/7 coverage across multiple time zones',
    '- Reduced estimating turnaround by 60% for clients',
    '',
    'CLOSE TECHNIQUE:',
    'Would it make sense to walk through one of your recent projects',
    'and see if we could compress timeline or free up your team?',
    'Takes 20 minutes. When works for you this week?',
]
create_pdf('data/knowledge_base/05-outreach-templates.pdf', 'Outreach Templates', content)

pdfs = sorted([f for f in os.listdir('data/knowledge_base') if f.endswith('.pdf')])
print(f"Successfully created {len(pdfs)} PDFs in data/knowledge_base/:")
for pdf in pdfs:
    print(f"  - {pdf}")
