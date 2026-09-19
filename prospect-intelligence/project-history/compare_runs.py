import json
from scoring.engine import score
from api.models import ResearchFindings, Finding, EvidenceLabel, SourceRef

def load_json(path):
    with open(path) as f:
        return json.load(f)

base = load_json("baseline_profiling_results.json")
opt_prof = load_json("optimized_profiling_results.json")
step1_api = load_json("benchmark_step1_results.json")

print("================================================================================")
print("1. COMPARING SCORE FACTORS & RAW FINDINGS FOR EDEN FACADES AND SPOTIFY")
print("================================================================================")

def compare_company(cname):
    b_c = next(c for c in base if c["company_name"] == cname)
    o_c = next(c for c in opt_prof if c["company_name"] == cname)
    s_c = next((c for c in step1_api if c["company_name"] == cname), None)
    
    print(f"\n--- {cname} ---")
    print(f"Scores across runs:")
    print(f"  Baseline: {b_c['lead_score']['total']} (Band: {b_c['lead_score']['band']})")
    print(f"  Optimized Profiling: {o_c['lead_score']['total']} (Band: {o_c['lead_score']['band']})")
    if s_c:
        print(f"  Optimized API (/prospects): {s_c['score_total']} (Band: {s_c['score_band']})")
        
    print("\nFactor-by-factor breakdown comparison:")
    b_factors = {f["factor"]: f for f in b_c["lead_score"]["breakdown"]}
    o_factors = {f["factor"]: f for f in o_c["lead_score"]["breakdown"]}
    s_factors = {f["factor"]: f for f in s_c["score_breakdown"]} if s_c else {}
    
    for factor_name, b_f in b_factors.items():
        o_f = o_factors.get(factor_name, {})
        s_f = s_factors.get(factor_name, {})
        b_pts = b_f.get("points_awarded", 0)
        o_pts = o_f.get("points_awarded", 0)
        s_pts = s_f.get("points_awarded", 0) if s_f else "N/A"
        diff = (b_pts != o_pts) or (s_f and b_pts != s_pts)
        flag = " [CHANGED]" if diff else ""
        print(f"  Factor: {factor_name:<28} | Baseline: {b_pts} pts | Opt: {o_pts} pts | API: {s_pts} pts{flag}")
        if diff:
            print(f"     Baseline evidence : {b_f.get('evidence')}")
            print(f"     Optimized evidence: {o_f.get('evidence')}")
            if s_f:
                print(f"     API evidence      : {s_f.get('evidence')}")

compare_company("Eden Facades Ltd")
compare_company("Spotify")
compare_company("Concept Facades Ltd")
compare_company("Harts Roofing")

print("\n================================================================================")
print("2. DETERMINISM CHECK (SCORE-03): RE-SCORING SAME FINDINGS MULTIPLE TIMES")
print("================================================================================")

# Let's test score determinism by passing the exact same ResearchFindings object 100 times
for comp in base:
    # Build ResearchFindings from breakdown
    findings_list = []
    for item in comp["lead_score"]["breakdown"]:
        # extract field and value from evidence: [field] = 'value'
        ev = item["evidence"]
        field_part = ev.split("] = ")[0].replace("[", "")
        val_part = ev.split("] = ")[1].strip("'")
        findings_list.append(Finding(field=field_part, value=val_part, label=EvidenceLabel.VERIFIED, sources=[]))
    
    rf = ResearchFindings(job_id="test", company_snapshot=findings_list)
    scores = [score(rf).total for _ in range(20)]
    all_same = len(set(scores)) == 1
    print(f"{comp['company_name']:<25}: Deterministic repeat check (20 runs) -> {scores[0]} pts (All identical: {all_same})")

print("\n================================================================================")
print("3. RESEARCH DEPTH & SOURCE COUNTS COMPARISON")
print("================================================================================")

print(f"{'Company':<25} | {'Baseline Sources':<18} | {'Optimized Sources':<18} | {'API Final Sources':<18}")
print("-" * 85)
for comp in base:
    cname = comp["company_name"]
    o_c = next(c for c in opt_prof if c["company_name"] == cname)
    s_c = next((c for c in step1_api if c["company_name"] == cname), None)
    
    b_count = len(comp["sources"])
    o_count = len(o_c["sources"])
    s_count = s_c["num_sources"] if s_c else "N/A"
    
    print(f"{cname:<25} | {b_count:<18} | {o_count:<18} | {s_count:<18}")
    print(f"  Baseline URLs : {comp['sources']}")
    print(f"  Optimized URLs: {o_c['sources']}")
    if s_c:
        async_urls = [s.get("url") for s in s_c.get("sources", [])]
        print(f"  API Brief Sources Count: {s_c['num_sources']}")
    print()
