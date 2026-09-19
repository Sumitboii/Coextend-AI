"""
Export Coextend Prospect Intelligence SQLite database to a polished multi-sheet Excel (.xlsx) file
using native sqlite3 and openpyxl.
"""
import sqlite3
import os
import json
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "prospect_intelligence.db")
OUTPUT_PATH_1 = os.path.join(os.path.dirname(__file__), "data", "Coextend_Prospect_Intelligence_Data.xlsx")
OUTPUT_PATH_2 = os.path.join(os.path.dirname(__file__), "..", "Project_PDFs_and_Presentations", "Coextend_Prospect_Intelligence_Data.xlsx")
OUTPUT_PATH_3 = os.path.join(os.path.dirname(__file__), "..", "Coextend_Prospect_Intelligence_Data.xlsx")

def export_to_excel():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    wb = openpyxl.Workbook()
    wb.remove(wb.active) # Remove initial default sheet

    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid") # Navy Blue
    
    high_fill = PatternFill(start_color="D9EAD3", end_color="D9EAD3", fill_type="solid") # Soft Green
    med_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")  # Soft Yellow
    low_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")  # Soft Gray
    
    body_font = Font(name="Segoe UI", size=10)
    bold_font = Font(name="Segoe UI", size=10, bold=True)
    
    thin_border = Border(
        left=Side(style='thin', color='E0E0E0'),
        right=Side(style='thin', color='E0E0E0'),
        top=Side(style='thin', color='E0E0E0'),
        bottom=Side(style='thin', color='E0E0E0')
    )

    # -------------------------------------------------------------
    # Sheet 1: Ranked Prospects Overview (from vw_jobs_by_score_desc + CRM hook)
    # -------------------------------------------------------------
    ws1 = wb.create_sheet(title="Ranked_Prospects")
    ws1.views.sheetView[0].showGridLines = True
    
    headers_1 = [
        "Rank", "Company Name", "Website", "Total Score (0-100)", "Priority Band", 
        "Recommended Service", "Job Status", "Created At", "Job ID"
    ]
    ws1.append(headers_1)
    
    query_1 = """
    SELECT 
        j.company_name,
        j.website,
        COALESCE(s.total_score, 0) AS total_score,
        COALESCE(s.priority_band, 'Unscored') AS priority_band,
        COALESCE(c.recommended_service, 'General Façade Advisory') AS recommended_service,
        j.status,
        j.created_at,
        j.job_id
    FROM jobs j
    LEFT JOIN lead_scores s ON j.job_id = s.job_id
    LEFT JOIN crm_exports c ON j.job_id = c.job_id
    ORDER BY s.total_score DESC NULLS LAST, j.created_at DESC;
    """
    cursor.execute(query_1)
    rows_1 = cursor.fetchall()
    
    for idx, r in enumerate(rows_1, start=1):
        ws1.append([idx, r[0], r[1], r[2], r[3], r[4], r[5], str(r[6])[:19], r[7]])

    # -------------------------------------------------------------
    # Sheet 2: Priority Summary (from vw_jobs_by_band)
    # -------------------------------------------------------------
    ws2 = wb.create_sheet(title="Priority_Summary")
    ws2.views.sheetView[0].showGridLines = True
    
    headers_2 = ["Priority Band", "Total Prospects", "Avg Score", "Min Score", "Max Score"]
    ws2.append(headers_2)
    
    cursor.execute("SELECT priority_band, count, avg_score, min_score, max_score FROM vw_jobs_by_band;")
    for r in cursor.fetchall():
        ws2.append(list(r))

    # -------------------------------------------------------------
    # Sheet 3: Lead Scores Detailed Breakdown
    # -------------------------------------------------------------
    ws3 = wb.create_sheet(title="Lead_Scores")
    ws3.views.sheetView[0].showGridLines = True
    
    headers_3 = [
        "Job ID", "Rubric Version", "Total Score", "Priority Band", 
        "Core Business Fit", "Commercial Alignment", "Strategic Trigger", "Zero Evidence Factors", "Scored At"
    ]
    ws3.append(headers_3)
    
    cursor.execute("SELECT job_id, rubric_version, total_score, priority_band, breakdown_json, zero_evidence_factors_json, created_at FROM lead_scores ORDER BY total_score DESC;")
    for r in cursor.fetchall():
        # Parse breakdown JSON if possible
        b_core, b_comm, b_strat = "", "", ""
        try:
            bd = json.loads(r[4]) if r[4] else {}
            b_core = str(bd.get("core_business_fit", {}).get("score", ""))
            b_comm = str(bd.get("commercial_alignment", {}).get("score", ""))
            b_strat = str(bd.get("strategic_trigger", {}).get("score", ""))
        except Exception:
            pass
        
        ws3.append([r[0], r[1], r[2], r[3], b_core, b_comm, b_strat, r[5], str(r[6])[:19]])

    # -------------------------------------------------------------
    # Sheet 4: CRM Exports
    # -------------------------------------------------------------
    ws4 = wb.create_sheet(title="CRM_Exports")
    ws4.views.sheetView[0].showGridLines = True
    
    headers_4 = [
        "Company Name", "Domain", "Score", "Priority Band", "Lead Status",
        "Recommended Service", "Verified Contact Name", "Verified Contact Title",
        "Possible Duplicate", "Job ID", "Exported At"
    ]
    ws4.append(headers_4)
    
    cursor.execute("""
        SELECT company_name, domain, score, priority_band, lead_status,
               recommended_service, verified_contact_name, verified_contact_title,
               possible_duplicate, job_id, created_at
        FROM crm_exports
        ORDER BY score DESC;
    """)
    for r in cursor.fetchall():
        ws4.append([r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], "Yes" if r[8] else "No", r[9], str(r[10])[:19]])

    # -------------------------------------------------------------
    # Sheet 5: Prospect Intelligence Briefs
    # -------------------------------------------------------------
    ws5 = wb.create_sheet(title="Prospect_Briefs")
    ws5.views.sheetView[0].showGridLines = True
    
    headers_5 = [
        "Job ID", "Rendered Markdown Brief", "Created At"
    ]
    ws5.append(headers_5)
    
    cursor.execute("SELECT job_id, rendered_markdown, created_at FROM briefs ORDER BY created_at DESC;")
    for r in cursor.fetchall():
        ws5.append([r[0], r[1], str(r[2])[:19]])

    # -------------------------------------------------------------
    # Sheet 6: All Jobs
    # -------------------------------------------------------------
    ws6 = wb.create_sheet(title="All_Jobs")
    ws6.views.sheetView[0].showGridLines = True
    
    headers_6 = [
        "Job ID", "Company Name", "Website", "Status", 
        "Contact Name", "Contact Title", "Created At", "Updated At", "Error Message"
    ]
    ws6.append(headers_6)
    
    cursor.execute("""
        SELECT job_id, company_name, website, status, 
               known_contact_name, known_contact_title, created_at, updated_at, error_message
        FROM jobs
        ORDER BY created_at DESC;
    """)
    for r in cursor.fetchall():
        ws6.append([r[0], r[1], r[2], r[3], r[4], r[5], str(r[6])[:19], str(r[7])[:19], r[8]])

    # -------------------------------------------------------------
    # Sheet 7: Research Findings (Categorized Facts)
    # -------------------------------------------------------------
    ws7 = wb.create_sheet(title="Research_Findings")
    ws7.views.sheetView[0].showGridLines = True
    
    headers_7 = [
        "Finding ID", "Job ID", "Category", "Field", "Value", "Verification Label", "Created At"
    ]
    ws7.append(headers_7)
    
    cursor.execute("""
        SELECT id, job_id, category, field, value, label, created_at
        FROM findings
        ORDER BY job_id, id;
    """)
    for r in cursor.fetchall():
        ws7.append([r[0], r[1], r[2], r[3], r[4], r[5], str(r[6])[:19]])

    # -------------------------------------------------------------
    # Sheet 8: Failed Jobs (Audit View)
    # -------------------------------------------------------------
    ws8 = wb.create_sheet(title="Failed_Jobs")
    ws8.views.sheetView[0].showGridLines = True
    
    headers_8 = ["Job ID", "Company Name", "Website", "Status", "Error Message", "Created At", "Updated At"]
    ws8.append(headers_8)
    
    cursor.execute("SELECT job_id, company_name, website, status, error_message, created_at, updated_at FROM vw_failed_jobs;")
    for r in cursor.fetchall():
        ws8.append([r[0], r[1], r[2], r[3], r[4], str(r[5])[:19], str(r[6])[:19]])

    # -------------------------------------------------------------
    # Sheet 9: Feedback
    # -------------------------------------------------------------
    ws9 = wb.create_sheet(title="Feedback")
    ws9.views.sheetView[0].showGridLines = True
    
    headers_9 = [
        "Feedback ID", "Job ID", "Company Name", "Website", "Total Score", "Priority Band",
        "Score Accuracy", "Brief Quality", "Outreach Quality", "User Comment", "Submitted By", "Submitted At"
    ]
    ws9.append(headers_9)

    # Check if feedback table exists before querying
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feedback';")
    if cursor.fetchone():
        query_9 = """
        SELECT 
            f.feedback_id,
            f.job_id,
            j.company_name,
            j.website,
            COALESCE(s.total_score, 0) AS total_score,
            COALESCE(s.priority_band, 'Unscored') AS priority_band,
            f.score_accuracy,
            f.brief_quality,
            f.outreach_quality,
            f.comment,
            f.submitted_by,
            f.created_at
        FROM feedback f
        JOIN jobs j ON f.job_id = j.job_id
        LEFT JOIN lead_scores s ON f.job_id = s.job_id
        ORDER BY f.created_at DESC;
        """
        cursor.execute(query_9)
        for r in cursor.fetchall():
            ws9.append([
                r[0], r[1], r[2], r[3], r[4], r[5],
                r[6], r[7], r[8], r[9] or "", r[10] or "", str(r[11])[:19]
            ])

    conn.close()

    # -------------------------------------------------------------
    # Apply Global Formatting to all sheets
    # -------------------------------------------------------------
    for ws in wb.worksheets:
        # Style Header
        ws.row_dimensions[1].height = 28
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Style Rows
        for row_idx in range(2, ws.max_row + 1):
            ws.row_dimensions[row_idx].height = 20
            for col_idx in range(1, ws.max_column + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.font = body_font
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")
                
                # Check Priority Band color
                val_str = str(cell.value or '').strip().upper()
                if val_str in ["HIGH", "TIER 1"]:
                    cell.fill = high_fill
                    cell.font = bold_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif val_str in ["MEDIUM", "TIER 2"]:
                    cell.fill = med_fill
                    cell.font = bold_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                elif val_str in ["LOW", "TIER 3"]:
                    cell.fill = low_fill
                    cell.font = bold_font
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                
                # Center numeric / short code columns
                col_header = str(ws.cell(row=1, column=col_idx).value or '')
                if any(k in col_header for k in ["Score", "Rank", "Count", "Total", "Status", "Min", "Max", "Band", "Tier"]):
                    if val_str not in ["HIGH", "MEDIUM", "LOW", "TIER 1", "TIER 2", "TIER 3"]:
                        cell.alignment = Alignment(horizontal="center", vertical="center")

        # Column widths auto-adjustment
        for col in ws.columns:
            col_letter = get_column_letter(col[0].column)
            header_text = str(col[0].value or '')
            
            if header_text in ["Rendered Markdown Brief", "Error Message", "Pain Points Summary"]:
                ws.column_dimensions[col_letter].width = 45
                continue

            max_len = 0
            for cell in col:
                v = str(cell.value or '')
                if '\n' in v:
                    v = max(v.split('\n'), key=len)
                max_len = max(max_len, len(v))
            
            ws.column_dimensions[col_letter].width = min(max(max_len + 3, 12), 65)

    # Save to multiple convenient destinations
    for out_path in [OUTPUT_PATH_1, OUTPUT_PATH_2, OUTPUT_PATH_3]:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        wb.save(out_path)
        print(f"Saved Excel file: {out_path}")

    print("Export finished successfully!")

if __name__ == "__main__":
    export_to_excel()
