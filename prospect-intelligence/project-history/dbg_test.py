import asyncio

async def test():
    from config import settings
    settings.demo_mode = False
    from api.models import ProspectRequest
    from engine.researcher import run_research, _extract_findings
    from engine.web_utils import web_search, fetch_page
    from scoring.engine import score

    req = ProspectRequest(company_name="Classic Marble", website="https://classicmarble.com")

    # --- Raw Gemini inspection ---
    print("=== RAW GEMINI OUTPUT TEST ===")
    try:
        pages = [{"url": "https://classicmarble.com", "text": "Classic Marble is a UK-based marble and stone contractor specialising in facade cladding, flooring, and interior fit-out. They work on high-end residential and commercial projects. Contact: John Smith, Managing Director. Turnover approx £10m. Staff: approx 80."}]
        snippets = [{"title": "Classic Marble", "link": "https://classicmarble.com", "snippet": "UK marble contractor, facade, cladding, stone flooring"}]
        raw = await _extract_findings("Classic Marble", "https://classicmarble.com", pages, snippets)
        import json
        print("RAW JSON from Gemini:")
        print(json.dumps(raw, indent=2)[:3000])
    except Exception as e:
        print(f"ERROR calling _extract_findings: {e}")
    print("=== END RAW ===\n")
    print("Running live research (this calls Gemini + Tavily)...")
    findings = await run_research("dbg-001", req)

    print("\nAll snapshot fields returned by Gemini:")
    for f in findings.company_snapshot:
        print(f"  field={f.field!r:40} [{f.label.value}] {f.value[:55]!r}")

    print("\nDecision makers:")
    for f in findings.decision_makers:
        print(f"  field={f.field!r} value={f.value[:60]!r}")

    print("\nProjects/signals:")
    for f in findings.projects_signals:
        print(f"  field={f.field!r} value={f.value[:60]!r}")

    print("\nNotes missing:", findings.notes_missing[:3])

    ls = score(findings)
    print("\nScore:", ls.total, "/ 100  Band:", ls.band)
    print("Zero evidence factors:", ls.zero_evidence_factors)
    print("Breakdown:")
    for f in ls.breakdown:
        print(f"  {f.factor:<35} {f.points_awarded:>2}/{f.weight}")

asyncio.run(test())
