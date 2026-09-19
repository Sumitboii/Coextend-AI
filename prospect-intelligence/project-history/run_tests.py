"""
run_tests.py — Full test suite for the Coextend Prospect Intelligence MVP.
Run against a live server at http://localhost:8000.

Usage:
    cd "c:\\Users\\ssing\\OneDrive\\Desktop\\Project Files\\Coextend AI\\prospect-intelligence"
    .venv\\Scripts\\python.exe run_tests.py 2>&1
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from typing import Any

import requests

BASE = "http://localhost:8000/api/v1"
JOB_ID = "06733c2d-f548-4c6d-9d56-bbf98847159a"
DB_PATH = "data/prospect_intelligence.db"

# ── Result tracking ─────────────────────────────────────────────────────────
results: dict[str, tuple[str, str]] = {}  # label -> (PASS|FAIL, notes)

def ok(label: str, notes: str = "") -> None:
    print(f"  [PASS] {label}" + (f" -- {notes}" if notes else ""))
    results[label] = ("PASS", notes)

def fail(label: str, detail: str = "") -> None:
    print(f"  [FAIL] {label}" + (f" -- {detail}" if detail else ""))
    results[label] = ("FAIL", detail)

def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

# ── Helpers ──────────────────────────────────────────────────────────────────

def poll_job(job_id: str, max_seconds: int = 120) -> dict | None:
    """Poll GET /prospects/{job_id} until status is complete or failed."""
    deadline = time.time() + max_seconds
    interval = 5
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/prospects/{job_id}", timeout=15)
            if r.status_code == 200:
                data = r.json()
                status = data.get("status", "")
                print(f"    polling … status={status}")
                if status in ("complete", "failed"):
                    return data
            else:
                print(f"    poll returned HTTP {r.status_code}")
        except Exception as exc:
            print(f"    poll error: {exc}")
        time.sleep(interval)
    return None


# ============================================================
# TEST 1 — E2E Pipeline (existing completed job)
# ============================================================

def test_e2e():
    section("TEST 1 — E2E Full Pipeline (job 06733c2d…)")

    # -- 1. Job record (Req 1.1) ------------------------------------------------
    try:
        r = requests.get(f"{BASE}/prospects/{JOB_ID}", timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        job = r.json()
    except Exception as exc:
        fail("Req 1.1 job record fetch", str(exc))
        return False

    for field in ("job_id", "status", "created_at", "company_name", "website", "duplicate_warning"):
        if field in job:
            ok(f"Req 1.1 job field '{field}'", f"value={repr(job[field])[:60]}")
        else:
            fail(f"Req 1.1 job field '{field}'", "field missing from job response")

    if job.get("status") != "complete":
        fail("Req 1.1 job status=complete", f"actual status={job.get('status')}")
    else:
        ok("Req 1.1 job status=complete")

    # -- 2. Brief (Req 5.1) -----------------------------------------------------
    try:
        r = requests.get(f"{BASE}/prospects/{JOB_ID}/brief", timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        brief = r.json()
    except Exception as exc:
        fail("Req 5.1 brief fetch", str(exc))
        return False

    required_sections = [
        "snapshot", "contact", "company_research", "projects_signals",
        "likely_requirements", "pain_point_hypotheses", "lead_score",
        "recommended_approach", "risks_unknowns", "next_action", "sources",
    ]
    for sec in required_sections:
        if sec in brief:
            ok(f"Req 5.1 brief section '{sec}'")
        else:
            fail(f"Req 5.1 brief section '{sec}'", "section missing")

    # -- 3. Req 4.1: exactly 10 score factors -----------------------------------
    lead_score = brief.get("lead_score", {})
    breakdown = lead_score.get("breakdown", [])
    if len(breakdown) == 10:
        ok("Req 4.1 lead_score.breakdown has exactly 10 factors")
    else:
        fail("Req 4.1 lead_score.breakdown has exactly 10 factors",
             f"actual={len(breakdown)}")

    # -- 4. Req 4.2: total in [0,100], band in High/Medium/Low -----------------
    total = lead_score.get("total")
    band = lead_score.get("band")
    if total is not None and 0 <= total <= 100:
        ok("Req 4.2 lead_score.total in [0,100]", f"total={total}")
    else:
        fail("Req 4.2 lead_score.total in [0,100]", f"actual total={total}")
    if band in ("High", "Medium", "Low"):
        ok("Req 4.2 lead_score.band valid", f"band={band}")
    else:
        fail("Req 4.2 lead_score.band valid", f"actual band={repr(band)}")

    # -- 5. Req 4.4: rubric_version present and non-empty ----------------------
    rv = lead_score.get("rubric_version")
    if rv and str(rv).strip():
        ok("Req 4.4 rubric_version present", f"version={rv}")
    else:
        fail("Req 4.4 rubric_version present", f"actual={repr(rv)}")

    # -- 6. Req 5.2: findings have 'label' field --------------------------------
    missing_label_errors = []
    for section_key in ("projects_signals", "likely_requirements", "pain_point_hypotheses"):
        items = brief.get(section_key, [])
        for i, item in enumerate(items):
            if "label" not in item:
                missing_label_errors.append(f"{section_key}[{i}] missing 'label'")

    if not missing_label_errors:
        ok("Req 5.2 all findings have 'label' field")
    else:
        fail("Req 5.2 all findings have 'label' field",
             "; ".join(missing_label_errors[:5]))

    # -- 7. Req 5.4: sources list not empty ------------------------------------
    sources = brief.get("sources", [])
    if sources:
        ok("Req 5.4 sources list not empty", f"count={len(sources)}")
    else:
        fail("Req 5.4 sources list not empty", "sources is empty or missing")

    # -- 8. Req 5.5: lead_score has total and breakdown -------------------------
    if "total" in lead_score and "breakdown" in lead_score:
        ok("Req 5.5 lead_score has total and breakdown")
    else:
        fail("Req 5.5 lead_score has total and breakdown",
             f"keys present={list(lead_score.keys())}")

    # -- 9. CRM export (Req 6.1) -----------------------------------------------
    try:
        r = requests.get(f"{BASE}/prospects/{JOB_ID}/crm-export", timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        crm = r.json()
    except Exception as exc:
        fail("Req 6.1 CRM export fetch", str(exc))
        crm = {}

    if crm:
        if "lead_score_total" in crm:
            ok("Req 6.1 crm.lead_score_total present", f"value={crm['lead_score_total']}")
        else:
            fail("Req 6.1 crm.lead_score_total present", "field missing")

        if "lead_score_band" in crm:
            ok("Req 6.1 crm.lead_score_band present", f"value={crm['lead_score_band']}")
        else:
            fail("Req 6.1 crm.lead_score_band present", "field missing")

        company_fields = crm.get("company_fields", {})
        if "name" in company_fields:
            ok("Req 6.1 crm.company_fields.name present", f"value={repr(company_fields['name'])}")
        else:
            fail("Req 6.1 crm.company_fields.name present",
                 f"keys present={list(company_fields.keys())}")

    # -- 10. Req 6.8: crm_adapter uses only MockHubSpotAdapter, no live HTTP ---
    try:
        with open("api/crm_adapter.py", encoding="utf-8") as f:
            adapter_src = f.read()

        # Look for requests.get/post/put/delete or httpx.get/post in export method
        # We check the whole file since import-level usage is also a concern
        live_http_patterns = [
            r"\brequests\.(get|post|put|delete|patch|head|request)\s*\(",
            r"\bhttpx\.(get|post|put|delete|patch|head|request|AsyncClient)\s*\(",
            r"\baiohttp\.(ClientSession|request)\s*\(",
        ]
        found_patterns = []
        for pattern in live_http_patterns:
            matches = re.findall(pattern, adapter_src)
            if matches:
                found_patterns.append(f"pattern '{pattern}' matched: {matches}")

        if not found_patterns:
            ok("Req 6.8 MockHubSpotAdapter makes no live HTTP calls")
        else:
            fail("Req 6.8 MockHubSpotAdapter makes no live HTTP calls",
                 "; ".join(found_patterns))
    except Exception as exc:
        fail("Req 6.8 MockHubSpotAdapter makes no live HTTP calls", str(exc))

    # -- 11. Outreach (Req 7.4, 7.1) ------------------------------------------
    try:
        r = requests.post(f"{BASE}/prospects/{JOB_ID}/outreach", timeout=30)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        outreach = r.json()
    except Exception as exc:
        fail("Req 7.4 outreach fetch", str(exc))
        outreach = {}

    if outreach:
        if outreach.get("status") == "draft":
            ok("Req 7.4 outreach.status == 'draft'")
        else:
            fail("Req 7.4 outreach.status == 'draft'",
                 f"actual={repr(outreach.get('status'))}")

        review_note = outreach.get("review_note")
        if review_note and str(review_note).strip():
            ok("Req 7.4 review_note is present", f"value={repr(review_note)[:80]}")
        else:
            fail("Req 7.4 review_note is present", f"actual={repr(review_note)}")

        li_msg = outreach.get("linkedin_message", "")
        if len(li_msg) <= 300:
            ok("Req 7.1 linkedin_message <= 300 chars", f"length={len(li_msg)}")
        else:
            fail("Req 7.1 linkedin_message <= 300 chars",
                 f"length={len(li_msg)} (over by {len(li_msg)-300})")

    return True


# ============================================================
# TEST 2 — FAB-01: Anti-fabrication (missing evidence)
# ============================================================

def test_fab01():
    section("TEST 2 — FAB-01: Anti-fabrication (fake company)")

    body = {
        "company_name": "XYZNONEXISTENT99 Ltd",
        "website": "https://xyznonexistent99fake.co.uk",
    }

    try:
        r = requests.post(f"{BASE}/prospects", json=body, timeout=15)
        assert r.status_code in (200, 202), f"HTTP {r.status_code}: {r.text[:200]}"
        job = r.json()
        fake_job_id = job.get("job_id")
        if not fake_job_id:
            fail("FAB-01 job submitted", f"No job_id in response: {job}")
            return
        ok("FAB-01 job submitted", f"job_id={fake_job_id}")
    except Exception as exc:
        fail("FAB-01 job submitted", str(exc))
        return

    print(f"  Polling for up to 120s … job_id={fake_job_id}")
    final = poll_job(fake_job_id, max_seconds=120)

    if final is None:
        fail("FAB-01 job completed within 120s", "timed out")
        return

    status = final.get("status")
    if status == "failed":
        error_msg = final.get("error_message", "")
        if error_msg and str(error_msg).strip():
            ok("FAB-01 graceful failure (error_message set)", f"error={repr(error_msg)[:120]}")
        else:
            fail("FAB-01 graceful failure (error_message set)",
                 f"job failed but error_message is empty or missing: {error_msg!r}")
        return

    if status == "complete":
        ok("FAB-01 job completed")
        try:
            r = requests.get(f"{BASE}/prospects/{fake_job_id}/brief", timeout=10)
            assert r.status_code == 200, f"HTTP {r.status_code}"
            brief = r.json()
        except Exception as exc:
            fail("FAB-01 brief fetch", str(exc))
            return

        # snapshot.company_name must match submitted name (not fabricated)
        snap_name = brief.get("snapshot", {}).get("company_name", "")
        submitted_name = body["company_name"]
        if snap_name.strip().lower() == submitted_name.strip().lower():
            ok("FAB-01 snapshot.company_name matches submitted name", f"name={snap_name!r}")
        else:
            fail("FAB-01 snapshot.company_name matches submitted name",
                 f"submitted={submitted_name!r} but got {snap_name!r}")

        # Req 10.2: At least one section contains "no evidence" OR score is 0
        brief_text = json.dumps(brief).lower()
        score_total = brief.get("lead_score", {}).get("total", -1)
        has_no_evidence = "no evidence" in brief_text
        score_is_zero = (score_total == 0)
        if has_no_evidence or score_is_zero:
            ok("Req 10.2 no-evidence or zero-score for fake company",
               f"score={score_total}, has_no_evidence={has_no_evidence}")
        else:
            fail("Req 10.2 no-evidence or zero-score for fake company",
                 f"score={score_total}, no 'no evidence' found in brief — possible fabrication")

        # notes_missing non-empty
        # Try fetching from DB
        try:
            conn = sqlite3.connect(DB_PATH)
            row = conn.execute(
                "SELECT findings_json FROM jobs WHERE job_id=? LIMIT 1",
                (fake_job_id,)
            ).fetchone()
            conn.close()
            if row and row[0]:
                findings_data = json.loads(row[0])
                notes_missing = findings_data.get("notes_missing", [])
                if notes_missing:
                    ok("FAB-01 notes_missing non-empty", f"entries={notes_missing[:3]}")
                else:
                    fail("FAB-01 notes_missing non-empty",
                         "notes_missing is empty — missing evidence not recorded")
            else:
                fail("FAB-01 notes_missing check", "findings_json not found in DB")
        except Exception as exc:
            fail("FAB-01 notes_missing check (DB)", str(exc))

        # lead_score.total should be 0 or very low (<=20) for no-evidence company
        if score_total <= 20:
            ok("FAB-01 lead_score.total low for fake company", f"total={score_total}")
        else:
            fail("FAB-01 lead_score.total low for fake company",
                 f"total={score_total} (expected <=20 for no-evidence company)")
    else:
        fail("FAB-01 job completed or failed", f"unexpected status={status}")


# ============================================================
# TEST 3 — SCORE-03: Score repeatability
# ============================================================

def test_score_repeatability():
    section("TEST 3 — SCORE-03: Score repeatability")

    # Import scoring from project (must run from project root)
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT findings_json, score_json FROM jobs WHERE job_id=? LIMIT 1",
            (JOB_ID,),
        ).fetchone()
        conn.close()
    except Exception as exc:
        fail("SCORE-03 DB read", str(exc))
        return

    if not row or not row[0]:
        fail("SCORE-03 DB read", f"No findings_json for job {JOB_ID}")
        return

    try:
        from api.models import ResearchFindings
        from scoring.engine import score

        findings = ResearchFindings(**json.loads(row[0]))
        score_a = score(findings)
        score_b = score(findings)
    except Exception as exc:
        fail("SCORE-03 score() invocation", str(exc))
        return

    passed = True

    if score_a.total == score_b.total:
        ok("SCORE-03 total is identical", f"total={score_a.total}")
    else:
        fail("SCORE-03 total is identical", f"a={score_a.total} vs b={score_b.total}")
        passed = False

    if score_a.band == score_b.band:
        ok("SCORE-03 band is identical", f"band={score_a.band}")
    else:
        fail("SCORE-03 band is identical", f"a={score_a.band} vs b={score_b.band}")
        passed = False

    if score_a.rubric_version == score_b.rubric_version:
        ok("SCORE-03 rubric_version identical", f"version={score_a.rubric_version}")
    else:
        fail("SCORE-03 rubric_version identical",
             f"a={score_a.rubric_version} vs b={score_b.rubric_version}")
        passed = False

    factor_diffs = []
    for i, (fa, fb) in enumerate(zip(score_a.breakdown, score_b.breakdown)):
        if fa.points_awarded != fb.points_awarded:
            factor_diffs.append(
                f"factor[{i}] '{fa.factor}': a={fa.points_awarded} vs b={fb.points_awarded}"
            )
    if not factor_diffs:
        ok("SCORE-03 all factor points identical")
    else:
        fail("SCORE-03 all factor points identical", "; ".join(factor_diffs))
        passed = False

    if passed:
        ok("SCORE-03 score repeatability — all checks passed")


# ============================================================
# TEST 4 — FAIL-03: Malformed request validation (422)
# ============================================================

def test_malformed_inputs():
    section("TEST 4 — FAIL-03: Malformed request validation")

    cases = [
        ("missing company_name",   {"website": "https://example.com"}),
        ("empty company_name",     {"company_name": "", "website": "https://example.com"}),
        ("bad URL scheme (ftp)",   {"company_name": "Test", "website": "ftp://example.com"}),
        ("not a URL at all",       {"company_name": "Test", "website": "not-a-url"}),
    ]

    passed_count = 0
    for name, body in cases:
        try:
            r = requests.post(f"{BASE}/prospects", json=body, timeout=10)
            if r.status_code == 422:
                data = r.json()
                if "detail" in data:
                    ok(f"FAIL-03 '{name}' → 422 with detail",
                       f"first error: {str(data['detail'])[:100]}")
                    passed_count += 1
                else:
                    fail(f"FAIL-03 '{name}' → 422 with detail",
                         f"got 422 but no 'detail' field — body={str(data)[:100]}")
            else:
                fail(f"FAIL-03 '{name}' → 422 with detail",
                     f"expected 422, got {r.status_code} — body={r.text[:120]}")
        except Exception as exc:
            fail(f"FAIL-03 '{name}' → 422 with detail", str(exc))

    total_label = f"FAIL-03 overall ({passed_count}/{len(cases)} passed)"
    if passed_count == len(cases):
        ok(total_label)
    else:
        fail(total_label)

    return passed_count, len(cases)


# ============================================================
# TEST 5 — API base path check
# ============================================================

def test_api_base_path():
    section("TEST 5 — API base path check (/api/v1)")

    endpoints_to_check = [
        ("GET", "/api/v1/health"),
        ("GET", f"/api/v1/prospects/{JOB_ID}"),
        ("GET", f"/api/v1/prospects/{JOB_ID}/brief"),
        ("GET", f"/api/v1/prospects/{JOB_ID}/crm-export"),
    ]

    for method, path in endpoints_to_check:
        url = f"http://localhost:8000{path}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code in (200, 201, 202):
                ok(f"API-PATH {method} {path} → {r.status_code}")
            elif r.status_code == 409:
                # 409 means resource exists but not ready — the path is correct
                ok(f"API-PATH {method} {path} → 409 (path valid, resource not ready)")
            else:
                fail(f"API-PATH {method} {path} → {r.status_code}",
                     f"expected 200-range, got {r.status_code}: {r.text[:100]}")
        except Exception as exc:
            fail(f"API-PATH {method} {path}", str(exc))

    # Wrong prefixes should return 404
    wrong_prefix = [
        ("GET", "/prospects/health"),
        ("GET", "/v1/health"),
    ]
    for method, path in wrong_prefix:
        url = f"http://localhost:8000{path}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 404:
                ok(f"API-PATH wrong prefix {path} → 404 (correctly not found)")
            else:
                fail(f"API-PATH wrong prefix {path} → 404",
                     f"expected 404, got {r.status_code}: {r.text[:100]}")
        except Exception as exc:
            fail(f"API-PATH wrong prefix {path}", str(exc))


# ============================================================
# TEST 6 — Req 1.8: GET non-existent job returns 404
# ============================================================

def test_nonexistent_job_404():
    section("TEST 6 — Req 1.8: GET non-existent job returns 404")

    fake_uuid = "00000000-0000-0000-0000-000000000000"
    url = f"{BASE}/prospects/{fake_uuid}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 404:
            ok("Req 1.8 GET /prospects/{missing_id} → 404",
               f"body={r.text[:80]}")
        else:
            fail("Req 1.8 GET /prospects/{missing_id} → 404",
                 f"expected 404, got {r.status_code}: {r.text[:100]}")
    except Exception as exc:
        fail("Req 1.8 GET /prospects/{missing_id} → 404", str(exc))


# ============================================================
# TEST 7 — Req 7.2: Outreach on incomplete job returns 409
# ============================================================

def test_outreach_on_pending_409():
    section("TEST 7 — Req 7.2: Outreach on pending/incomplete job returns 409")

    body = {"company_name": "Quick Test Co", "website": "https://example.com"}
    try:
        r = requests.post(f"{BASE}/prospects", json=body, timeout=10)
        assert r.status_code in (200, 202), f"HTTP {r.status_code}: {r.text[:200]}"
        job = r.json()
        new_job_id = job.get("job_id")
        if not new_job_id:
            fail("Req 7.2 outreach on pending job", f"No job_id in: {job}")
            return
        ok("Req 7.2 new job submitted", f"job_id={new_job_id}")
    except Exception as exc:
        fail("Req 7.2 new job submitted", str(exc))
        return

    # Immediately try outreach — job should be pending/researching, not complete
    try:
        r = requests.post(f"{BASE}/prospects/{new_job_id}/outreach", timeout=10)
        if r.status_code == 409:
            ok("Req 7.2 outreach on pending job → 409",
               f"body={r.text[:100]}")
        elif r.status_code == 200:
            # Might have finished instantly (very fast server or cached)
            fail("Req 7.2 outreach on pending job → 409",
                 f"got 200 — job may have completed instantly (race condition possible)")
        else:
            fail("Req 7.2 outreach on pending job → 409",
                 f"expected 409, got {r.status_code}: {r.text[:100]}")
    except Exception as exc:
        fail("Req 7.2 outreach on pending job → 409", str(exc))


# ============================================================
# SUMMARY
# ============================================================

def print_summary(fab01_status: str, fail03_fraction: str):
    print(f"\n{'='*65}")
    print("  === TEST SUMMARY ===")
    print(f"{'='*65}")
    print(f"  {'TEST':<35} {'RESULT':<8} NOTES")
    print(f"  {'-'*35} {'-'*8} {'-'*20}")

    def row(label: str, keys: list[str], override: str | None = None, notes: str = ""):
        if override:
            result = override
            note = notes
        else:
            sub_results = [results.get(k, ("UNKNOWN", "")) for k in keys if k in results]
            if not sub_results:
                result = "SKIP"
                note = "no checks ran"
            elif all(r[0] == "PASS" for r in sub_results):
                result = "PASS"
                note = notes
            else:
                failures = [f"{k}: {v[1]}" for k, v in results.items()
                            if k in keys and v[0] == "FAIL"]
                result = "FAIL"
                note = notes or f"{len(failures)} check(s) failed"
        print(f"  {label:<35} {result:<8} {note}")

    # Build grouped status
    e2e_keys = [k for k in results if k.startswith("Req 1.1") or k.startswith("Req 5.") or
                k.startswith("Req 4.") or k.startswith("Req 6.") or k.startswith("Req 7.4") or
                k.startswith("Req 7.1")]
    fab01_keys = [k for k in results if k.startswith("FAB-01")]
    score_keys = [k for k in results if k.startswith("SCORE-03")]
    fail03_keys = [k for k in results if k.startswith("FAIL-03") and "overall" not in k]
    api_path_keys = [k for k in results if k.startswith("API-PATH")]
    req18_keys = [k for k in results if k.startswith("Req 1.8")]
    req72_keys = [k for k in results if k.startswith("Req 7.2")]

    row("E2E-01 full pipeline",         e2e_keys)
    row("FAB-01 anti-fabrication",      fab01_keys, notes=fab01_status)
    row("SCORE-03 repeatability",       score_keys)
    row("FAIL-03 malformed inputs",     fail03_keys, notes=fail03_fraction)
    row("API-PATH base path check",     api_path_keys)
    row("REQ-1.8 404 on missing job",   req18_keys)
    row("REQ-7.2 409 on pending job",   req72_keys)

    print(f"\n  {'='*63}")
    print("  FLAWS FOUND:")
    flaws = [(label, detail) for label, (status, detail) in results.items()
             if status == "FAIL"]
    if flaws:
        for label, detail in flaws:
            req_ref = ""
            if label.startswith("Req "):
                parts = label.split()
                req_ref = f" [{parts[0]} {parts[1]}]"
            elif label.startswith("FAB-01"):
                req_ref = " [Req 10.2]"
            elif label.startswith("SCORE-03"):
                req_ref = " [Req 4.3]"
            elif label.startswith("FAIL-03"):
                req_ref = " [Req FAIL-03]"
            elif label.startswith("API-PATH"):
                req_ref = " [Req 1.5]"
            print(f"  - {label}{req_ref}: {detail[:120]}")
    else:
        print("  None — all checks passed!")
    print(f"  {'='*63}\n")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("\nCoextend Prospect Intelligence MVP — Full Test Suite")
    print(f"Target: {BASE}")
    print(f"Existing job: {JOB_ID}\n")

    # Check server is up
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        if r.status_code == 200:
            print("[OK] Server is reachable — starting tests\n")
        else:
            print(f"[WARN] /health returned {r.status_code}")
    except Exception as exc:
        print(f"[ERROR] Cannot reach server at {BASE}: {exc}")
        print("Aborting — please start the server first.")
        sys.exit(1)

    test_e2e()

    fab01_status = ""
    test_fab01()
    # Determine FAB-01 top-level result for summary
    fab01_keys = [k for k in results if k.startswith("FAB-01")]
    if any(results.get(k, ("FAIL",))[0] == "FAIL" for k in fab01_keys):
        fab01_status = "check details above"
    else:
        fab01_status = "no fabrication detected"

    test_score_repeatability()

    n_passed, n_total = test_malformed_inputs()
    fail03_fraction = f"({n_passed}/{n_total} passed)"

    test_api_base_path()
    test_nonexistent_job_404()
    test_outreach_on_pending_409()

    print_summary(fab01_status, fail03_fraction)
