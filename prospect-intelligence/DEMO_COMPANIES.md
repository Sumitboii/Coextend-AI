# Demo Companies — Try the Tool

Copy any company name + website below into the **"New Prospect"** form to test the Prospect Intelligence tool. Just paste the company name, paste the website URL, and click **"Start Research"** to see how the system evaluates different types of prospects.

## Ready-to-Use Company Examples

| Company Name | Website | Context |
|---|---|---|
| **Eden Facades Ltd** | https://edenfacades.com | Strong-fit UK façade contractor — well-established with good web presence. Scores in "A / Strong fit" (65-79) or "A+ / Priority" (80-100). |
| **Harley Facades Ltd** | https://www.harleyfacades.co.uk | Strong-fit UK curtain wall specialist — another good-fit example showing typical Tier A/A+ scoring contractor. |
| **Concept Facades Ltd** | https://conceptfacades.co.uk | Mid-fit UK façade company — demonstrates realistic assessment in "B / Nurture" (50-64) or "C / Low priority" (35-49). |
| **Spotify** | https://www.spotify.com | Poor-fit test case — clearly outside our ICP (music streaming, not construction). Scored in "D / Disqualify" (0-34). |
| **Harts Roofing** | https://www.hartsroofing.co.uk | Minimal web presence — tests anti-fabrication behavior in "D / Disqualify" ("no evidence found" rather than guessing). |

## How to Use

1. Open http://localhost:8000 in your browser
2. Click "New Prospect" (top right)
3. Copy a company name from the table above
4. Paste into the "Company Name" field
5. Copy the website URL
6. Paste into the "Website" field
7. Click "Start Research"
8. Watch the status indicator update (yellow → green)
9. View the research brief, lead score, and findings

## What You'll See

- **Research Brief**: Company overview, key findings, hypotheses, and tier recommended action
- **Lead Score**: 0-100 deterministic score with 5-tier classification (A+, A, B, C, D)
- **Source Verification**: Which sources were used (and which were rejected)
- **CRM Export**: HubSpot-formatted data ready to export with priority and lead band
- **Outreach Templates**: Email and LinkedIn message drafts

## Tips

- **Strong-fit companies** (Eden, Harley): Look for Tier A/A+ scores and rich findings
- **Mid-fit companies** (Concept): Notice the nuanced assessment in Tier B/C (not just yes/no)
- **Poor-fit companies** (Spotify): See how the tool correctly identifies non-prospects in Tier D
- **Minimal-web companies** (Harts): Observe the "no evidence found" behavior in Tier D — this is a feature, not a bug

## Questions?

- See **README.md** for full documentation
- Check **API docs** at http://localhost:8000/docs for endpoint details
- Review **SOURCE_VERIFICATION_FINAL_REPORT.md** for verification logic
