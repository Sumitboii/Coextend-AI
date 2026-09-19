import re

with open("engine/researcher.py", "r") as f:
    content = f.read()

# Update 1: Improve system prompt to cite pages explicitly
old_prompt = 'REQUIRED FIELD NAMES for company_snapshot:'
new_prompt = '''FOR EACH FIELD, cite the page URL where you found the information in source_urls.
If info appears on multiple pages, include all of them.
The pages in this research are labeled at the top like "=== PAGE: https://... ===".
Include those exact URLs in source_urls.

REQUIRED FIELD NAMES for company_snapshot:'''

content = content.replace(old_prompt, new_prompt)

# Update 2: Increase pages passed to LLM from 4 to 10
content = re.sub(r"for p in pages\\\[:4\\\]", "for p in pages[:10]", content)

# Update 3: Add logging after internal links extraction
log_line = '''        internal_links = _extract_internal_links(homepage_text, domain)
        pages_to_fetch.extend(internal_links[:5])  # Max 5 internal'''

log_line_new = '''        internal_links = _extract_internal_links(homepage_text, domain)
        logger.info("Extracted %d internal links from homepage: %s", len(internal_links), internal_links[:3])
        pages_to_fetch.extend(internal_links[:5])  # Max 5 internal'''

content = content.replace(log_line, log_line_new)

# Update 4: Add logging after all pages are fetched
log_line2 = '''    # 3. LLM structured extraction
    findings_raw = await _extract_findings(company, website, fetched_pages, unique_results)'''

log_line2_new = '''    # 3. LLM structured extraction
    logger.info("Fetched %d pages for LLM: %s", len(fetched_pages), [p["url"] for p in fetched_pages[:5]])
    findings_raw = await _extract_findings(company, website, fetched_pages, unique_results)'''

content = content.replace(log_line2, log_line2_new)

with open("engine/researcher.py", "w") as f:
    f.write(content)

print("✓ Updated researcher.py:")
print("  - Improved system prompt to explicitly cite page URLs")
print("  - Increased pages passed to LLM from 4 to 10")
print("  - Added logging for internal links extraction")
print("  - Added logging for fetched pages")
