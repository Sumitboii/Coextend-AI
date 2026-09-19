import os
import sys
import html
import zipfile
import xml.etree.ElementTree as ET
import docx
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
            doc_title = getattr(self, "doc_title", "Coextend AI Knowledge Base")
            self.drawString(40, 760, doc_title)
            self.drawRightString(572, 760, "Coextend Global LLP — Prospect Intelligence")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 752, 572, 752)
            
        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 42, 572, 42)
        
        self.drawString(40, 30, "Coextend AI — Confidential Internal Knowledge Document")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 30, page_text)
        self.restoreState()

def clean_text(t):
    if not t:
        return ""
    t = t.replace("\ufffd", "ç")
    t = t.replace("faade", "façade")
    t = t.replace("Faade", "Façade")
    return t

def get_styles():
    styles = getSampleStyleSheet()
    
    primary_color = colors.HexColor("#1E3A8A")   # Navy
    secondary_color = colors.HexColor("#0D9488") # Teal
    dark_slate = colors.HexColor("#1E293B")      # Slate 800
    subtle_slate = colors.HexColor("#475569")    # Slate 600
    
    styles.add(ParagraphStyle(
        name="DocTitleCustom",
        fontName="Arial-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceAfter=10
    ))
    
    styles.add(ParagraphStyle(
        name="Heading1Custom",
        fontName="Arial-Bold",
        fontSize=13,
        leading=17,
        textColor=primary_color,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True
    ))
    
    styles.add(ParagraphStyle(
        name="Heading2Custom",
        fontName="Arial-Bold",
        fontSize=10.5,
        leading=14,
        textColor=dark_slate,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        name="Heading3Custom",
        fontName="Arial-Bold",
        fontSize=9.5,
        leading=13,
        textColor=subtle_slate,
        spaceBefore=6,
        spaceAfter=3,
        keepWithNext=True
    ))
    
    styles.add(ParagraphStyle(
        name="BodyCustom",
        fontName="Arial",
        fontSize=9,
        leading=13,
        textColor=dark_slate,
        spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name="BulletCustom",
        fontName="Arial",
        fontSize=9,
        leading=13,
        textColor=dark_slate,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        name="TableCellCustom",
        fontName="Arial",
        fontSize=8,
        leading=11,
        textColor=dark_slate
    ))

    styles.add(ParagraphStyle(
        name="TableHeadCustom",
        fontName="Arial-Bold",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.white
    ))
    
    return styles

def runs_to_html(p):
    text_fragments = []
    for r in p.runs:
        t = clean_text(r.text)
        if not t:
            continue
        t = html.escape(t)
        if r.bold and r.italic:
            t = f"<b><i>{t}</i></b>"
        elif r.bold:
            t = f"<b>{t}</b>"
        elif r.italic:
            t = f"<i>{t}</i>"
        if r.underline:
            t = f"<u>{t}</u>"
        text_fragments.append(t)
    return "".join(text_fragments).strip()

def convert_docx_to_pdf(docx_path, pdf_path):
    print(f"Converting DOCX: {os.path.basename(docx_path)} -> {os.path.basename(pdf_path)}")
    doc = docx.Document(docx_path)
    styles = get_styles()
    
    doc_title = os.path.splitext(os.path.basename(docx_path))[0]
    
    pdf = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=54,
        bottomMargin=54
    )
    
    flowables = []
    
    for child in doc.element.body:
        tag = child.tag.split("}")[-1]
        
        if tag == "p":
            p = docx.text.paragraph.Paragraph(child, doc)
            text_html = runs_to_html(p)
            if not text_html:
                continue
            
            s_name = p.style.name.lower()
            if "title" in s_name:
                flowables.append(Paragraph(text_html, styles["DocTitleCustom"]))
                flowables.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=10))
            elif "heading 1" in s_name:
                flowables.append(Paragraph(text_html, styles["Heading1Custom"]))
            elif "heading 2" in s_name:
                flowables.append(Paragraph(text_html, styles["Heading2Custom"]))
            elif "heading 3" in s_name:
                flowables.append(Paragraph(text_html, styles["Heading3Custom"]))
            elif "bullet" in s_name:
                flowables.append(Paragraph(f"&bull; {text_html}", styles["BulletCustom"]))
            elif "number" in s_name:
                flowables.append(Paragraph(text_html, styles["BulletCustom"]))
            else:
                flowables.append(Paragraph(text_html, styles["BodyCustom"]))
                
        elif tag == "tbl":
            table = docx.table.Table(child, doc)
            num_rows = len(table.rows)
            if num_rows == 0:
                continue
            num_cols = len(table.columns)
            if num_cols == 0:
                continue
            
            table_width = 532
            col_widths = [table_width / num_cols] * num_cols
            if num_cols == 2:
                col_widths = [150, 382]
            elif num_cols == 3:
                col_widths = [130, 232, 170]
            elif num_cols == 4:
                col_widths = [110, 160, 140, 122]
                
            table_data = []
            for r_idx, row in enumerate(table.rows):
                row_cells = []
                for c_idx, cell in enumerate(row.cells):
                    cell_paras = []
                    for cp in cell.paragraphs:
                        chtml = runs_to_html(cp)
                        if chtml:
                            st = styles["TableHeadCustom"] if r_idx == 0 and num_rows > 1 else styles["TableCellCustom"]
                            cell_paras.append(Paragraph(chtml, st))
                    if not cell_paras:
                        cell_paras.append(Paragraph("&nbsp;", styles["TableCellCustom"]))
                    row_cells.append(cell_paras)
                table_data.append(row_cells)
                
            t_style = [
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A") if num_rows > 1 else colors.HexColor("#F1F5F9")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white if num_rows > 1 else colors.HexColor("#1E293B")),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ]
            if num_rows > 1:
                for r in range(1, num_rows):
                    if r % 2 == 0:
                        t_style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC")))
                        
            reportlab_table = Table(table_data, colWidths=col_widths, repeatRows=1 if num_rows > 1 else 0)
            reportlab_table.setStyle(TableStyle(t_style))
            flowables.append(Spacer(1, 4))
            flowables.append(reportlab_table)
            flowables.append(Spacer(1, 6))

    def canvas_maker(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.doc_title = doc_title
        return c

    pdf.build(flowables, canvasmaker=canvas_maker)
    print(f"Successfully generated {pdf_path}")

def convert_odt_to_pdf(odt_path, pdf_path):
    print(f"Converting ODT: {os.path.basename(odt_path)} -> {os.path.basename(pdf_path)}")
    styles = get_styles()
    doc_title = "Coextend AI - Pilot Project Brief"
    
    with zipfile.ZipFile(odt_path) as z:
        content = z.read('content.xml')
        tree = ET.fromstring(content)
        
    pdf = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=54,
        bottomMargin=54
    )
    
    flowables = []
    
    body = tree.find('.//{urn:oasis:names:tc:opendocument:xmlns:office:1.0}body')
    if body is not None and len(body) > 0:
        office_text = body[0]
        for elem in office_text:
            tag = elem.tag.split('}')[-1]
            text = clean_text(''.join(elem.itertext())).strip()
            
            if tag == 'p':
                if not text:
                    continue
                if 'COEXTEND AI AUTOMATION ENGINEER' in text or 'Pilot Project' in text:
                    flowables.append(Paragraph(html.escape(text), styles["DocTitleCustom"]))
                    flowables.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E3A8A"), spaceAfter=10))
                else:
                    flowables.append(Paragraph(html.escape(text), styles["BodyCustom"]))
            elif tag == 'h':
                if not text:
                    continue
                flowables.append(Paragraph(html.escape(text), styles["Heading1Custom"]))
            elif tag == 'list':
                for li in elem.iter('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}list-item'):
                    li_text = clean_text(''.join(li.itertext())).strip()
                    if li_text:
                        flowables.append(Paragraph(f"&bull; {html.escape(li_text)}", styles["BulletCustom"]))
            elif tag == 'table':
                table_rows = []
                for row in elem.iter('{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-row'):
                    row_cells = []
                    for cell in row.iter('{urn:oasis:names:tc:opendocument:xmlns:table:1.0}table-cell'):
                        c_text = clean_text(''.join(cell.itertext())).strip()
                        row_cells.append(c_text)
                    if any(row_cells):
                        table_rows.append(row_cells)
                
                if table_rows:
                    num_rows = len(table_rows)
                    num_cols = max(len(r) for r in table_rows)
                    col_widths = [532 / num_cols] * num_cols
                    if num_cols == 2:
                        col_widths = [150, 382]
                    elif num_cols == 3:
                        col_widths = [130, 232, 170]
                    
                    table_data = []
                    for r_idx, r in enumerate(table_rows):
                        r_paras = []
                        while len(r) < num_cols:
                            r.append("")
                        for c_idx, c_val in enumerate(r):
                            st = styles["TableHeadCustom"] if r_idx == 0 else styles["TableCellCustom"]
                            r_paras.append([Paragraph(html.escape(c_val) if c_val else "&nbsp;", st)])
                        table_data.append(r_paras)
                        
                    t_style = [
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                        ('TOPPADDING', (0,0), (-1,-1), 4),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                        ('LEFTPADDING', (0,0), (-1,-1), 5),
                        ('RIGHTPADDING', (0,0), (-1,-1), 5),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                    ]
                    for r in range(1, num_rows):
                        if r % 2 == 0:
                            t_style.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor("#F8FAFC")))
                            
                    reportlab_table = Table(table_data, colWidths=col_widths, repeatRows=1)
                    reportlab_table.setStyle(TableStyle(t_style))
                    flowables.append(Spacer(1, 4))
                    flowables.append(reportlab_table)
                    flowables.append(Spacer(1, 6))

    def canvas_maker(*args, **kwargs):
        c = NumberedCanvas(*args, **kwargs)
        c.doc_title = doc_title
        return c

    pdf.build(flowables, canvasmaker=canvas_maker)
    print(f"Successfully generated {pdf_path}")

def main():
    dir_path = r"C:\Users\ssing\OneDrive\Desktop\Project Files\Coextend AI"
    docx_files = [f for f in os.listdir(dir_path) if f.endswith(".docx")]
    
    for fname in sorted(docx_files):
        in_path = os.path.join(dir_path, fname)
        out_name = os.path.splitext(fname)[0] + ".pdf"
        out_path = os.path.join(dir_path, out_name)
        try:
            convert_docx_to_pdf(in_path, out_path)
        except Exception as e:
            print(f"Error converting {fname}: {e}")
            
    odt_file = "Coextend AI Automation Engineer - Pilot Project Brief.odt"
    odt_in = os.path.join(dir_path, odt_file)
    odt_out = os.path.join(dir_path, "Coextend AI Automation Engineer - Pilot Project Brief.pdf")
    if os.path.exists(odt_in):
        try:
            convert_odt_to_pdf(odt_in, odt_out)
        except Exception as e:
            print(f"Error converting {odt_file}: {e}")

if __name__ == "__main__":
    main()
