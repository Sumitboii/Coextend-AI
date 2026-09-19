import asyncio
import time
from api.models import ProspectRequest, JobStatus
from engine.researcher import run_research
from scoring.engine import score
from engine.brief_generator import generate_brief
from api.crm_adapter import MockHubSpotAdapter

async def profile_pipeline():
    req = ProspectRequest(
        company_name="Lindner Prater Ltd",
        website="https://www.lindner-group.com",
    )
    job_id = "test-profile-001"
    
    print(f"--- PROFILING PIPELINE FOR: {req.company_name} ---")
    t_start = time.time()
    
    # 1. Research
    t0 = time.time()
    findings = await run_research(job_id, req)
    t_research = time.time() - t0
    print(f"[1] Research Time: {t_research:.2f}s")
    
    # 2. Scoring
    t0 = time.time()
    lead_score = score(findings)
    t_score = time.time() - t0
    print(f"[2] Deterministic Scoring Time: {t_score*1000:.2f}ms (Score: {lead_score.total}, Band: {lead_score.band})")
    
    # 3. Brief Generation
    t0 = time.time()
    brief = await generate_brief(findings, lead_score)
    t_brief = time.time() - t0
    print(f"[3] Brief Generation Time: {t_brief:.2f}s")
    
    # 4. CRM Export
    t0 = time.time()
    crm = await MockHubSpotAdapter().export(brief)
    t_crm = time.time() - t0
    print(f"[4] CRM Export Time: {t_crm*1000:.2f}ms")
    
    t_total = time.time() - t_start
    print(f"\n>>> TOTAL TIME BEFORE OPTIMIZATION: {t_total:.2f}s <<<")

if __name__ == "__main__":
    asyncio.run(profile_pipeline())
