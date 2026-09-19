import re

with open("engine/researcher.py", "r") as f:
    lines = f.readlines()

# Find the section where we build findings - after the _adapt_gemini_response call
# We'll add source assignment logic AFTER adapt but BEFORE _parse_findings

# Look for the line with "company_snapshot = _normalise_scoring_fields(_parse_findings"
# and insert logic before it to assign sources

# First, let's find the exact location
for i, line in enumerate(lines):
    if "company_snapshot = _normalise_scoring_fields(_parse_findings(findings_raw.get" in line:
        print(f"Found target at line {i+1}")
        break
else:
    print("Target line not found")

# Now, let's add source assignment logic
# Insert BEFORE line that assigns company_snapshot
insert_pos = None
for i, line in enumerate(lines):
    if "company_snapshot = _normalise_scoring_fields(_parse_findings(findings_raw.get" in line:
        insert_pos = i
        break

if insert_pos:
    # Create new source assignment code
    new_code = '''    # Assign fetched page URLs to findings (since LLM may not cite them)
    # This ensures all findings reference the pages they came from
    all_fetched_urls = [p["url"] for p in fetched_pages]
    logger.info("Assigning sources: found %d fetched pages: %s", len(all_fetched_urls), all_fetched_urls[:3])
    
    # For each finding that lacks sources, assign the primary pages
    for findings_list in [findings_raw.get("company_snapshot", []), 
                          findings_raw.get("decision_makers", []),
                          findings_raw.get("projects_signals", [])]:
        for finding in findings_list:
            if isinstance(finding, dict):
                existing_urls = finding.get("source_urls", [])
                if not existing_urls and all_fetched_urls:
                    # Assign the main pages (exclude homepage, prefer internal)
                    internal_urls = [u for u in all_fetched_urls if u != website]
                    finding["source_urls"] = internal_urls if internal_urls else all_fetched_urls[:1]
                    logger.debug("Assigned sources to %s: %s", finding.get("field", "?"), finding["source_urls"][:2])
    
'''
    lines.insert(insert_pos, new_code)

with open("engine/researcher.py", "w") as f:
    f.writelines(lines)

print("✓ Added source assignment logic")
