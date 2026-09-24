"""
Execute live extraction test for 6 diverse real domains in forced fallback mode:
1. University: https://www.unipune.ac.in/
2. Government: https://www.gov.uk/
3. Hospital/Healthcare: https://www.nhs.uk/
4. Law firm: https://www.cliffordchance.com/
5. Non-profit/NGO: https://www.redcross.org.uk/
6. Façade contractor: https://www.harleyfacades.co.uk/
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent / "prospect-intelligence"))

from engine.researcher import _extract_heuristic_fallback
from engine.web_utils import fetch_page, web_search
from scoring.engine import score
from api.models import Finding, EvidenceLabel, ResearchFindings

TEST_DOMAINS = [
    {
        "category": "University",
        "company": "Savitribai Phule Pune University",
        "website": "https://www.unipune.ac.in/",
    },
    {
        "category": "Government",
        "company": "GOV.UK",
        "website": "https://www.gov.uk/",
    },
    {
        "category": "Hospital/Healthcare",
        "company": "NHS",
        "website": "https://www.nhs.uk/",
    },
    {
        "category": "Law firm",
        "company": "Clifford Chance",
        "website": "https://www.cliffordchance.com/",
    },
    {
        "category": "Non-Profit/NGO",
        "company": "British Red Cross",
        "website": "https://www.redcross.org.uk/",
    },
    {
        "category": "Façade Contractor",
        "company": "Eden Facades Ltd",
        "website": "https://www.edenfacades.co.uk/",
    },
]

async def test_domain(d):
    company = d["company"]
    website = d["website"]
    category = d["category"]

    print(f"\n========================================================")
    print(f"Testing Category: {category} | Company: {company} | Website: {website}")
    print(f"========================================================")

    # Fetch live page or search snippets
    try:
        page_text = await fetch_page(website, timeout=6.0)
    except Exception as exc:
        page_text = ""

    pages = [{"url": website, "text": page_text}] if page_text else []
    snippets = []
    try:
        snippets = await web_search(f'"{company}" about overview', num_results=3)
    except Exception:
        snippets = []

    # Run strictly in forced-fallback mode
    raw = _extract_heuristic_fallback(company, website, pages, snippets)

    trade_item = next(item for item in raw["company_snapshot"] if item["field"] == "trade_fit")
    sector_item = next(item for item in raw["company_snapshot"] if item["field"] == "sector")
    geo_item = next(item for item in raw["company_snapshot"] if item["field"] == "geography")
    dm_item = next(item for item in raw["decision_makers"] if item["field"] == "decision_maker_access")

    # Score
    findings = ResearchFindings(
        job_id=f"verify-{category.lower().replace('/', '-')}",
        company_snapshot=[Finding(field=i["field"], value=i["value"], label=EvidenceLabel.UNVERIFIED) for i in raw["company_snapshot"]],
        decision_makers=[Finding(field=i["field"], value=i["value"], label=EvidenceLabel.UNVERIFIED) for i in raw["decision_makers"]],
        projects_signals=[Finding(field=i["field"], value=i["value"], label=EvidenceLabel.UNVERIFIED) for i in raw["projects_signals"]],
    )
    s = score(findings)
    trade_factor = next(f for f in s.breakdown if f.factor == "trade_service_fit")

    res = {
        "category": category,
        "company": company,
        "website": website,
        "trade_fit": trade_item["value"],
        "sector": sector_item["value"],
        "label": trade_item["label"],
        "geography": geo_item["value"],
        "decision_maker": dm_item["value"],
        "trade_service_fit_points": trade_factor.points_awarded,
        "total_score": s.total,
        "band": s.band,
        "notes_missing_count": len(raw.get("notes_missing", [])),
    }

    print(json.dumps(res, indent=2))
    return res

async def main():
    results = []
    for d in TEST_DOMAINS:
        res = await test_domain(d)
        results.append(res)

    with open("forced_fallback_generalization_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved all results to forced_fallback_generalization_results.json")

if __name__ == "__main__":
    asyncio.run(main())
