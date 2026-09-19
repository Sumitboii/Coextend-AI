import asyncio
import time
from api.models import ProspectRequest
from engine.researcher import run_research
from scoring.engine import score
from engine.brief_generator import generate_brief

async def test_speed():
    req = ProspectRequest(company_name="Wipro", website="https://www.wipro.com")
    t0 = time.time()
    print("Starting research for Wipro...")
    findings = await run_research("test-speed-wipro", req)
    t1 = time.time()
    print(f"Research done in {t1 - t0:.2f}s")
    
    lead_score = score(findings)
    t2 = time.time()
    print(f"Scoring done in {t2 - t1:.2f}s (total: {t2 - t0:.2f}s)")
    
    brief = await generate_brief(findings, lead_score)
    t3 = time.time()
    print(f"Brief done in {t3 - t2:.2f}s (total: {t3 - t0:.2f}s)")

if __name__ == "__main__":
    asyncio.run(test_speed())
