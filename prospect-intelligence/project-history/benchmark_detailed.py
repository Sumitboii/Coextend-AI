"""
Detailed sub-component profiler for STEP 1 & STEP 2.
Directly instruments and times:
1. Tavily Search
2. Web page fetch (homepage + internal/external pages)
3. LLM Structured Extraction (Gemini)
4. Deterministic Scoring
5. RAG Retrieval / Embeddings & Vector lookup
6. Brief Generation LLM (Gemini)
7. Total Wall Clock & Stage Transitions
"""
import asyncio
import json
import time
from api.models import ProspectRequest
from api.database import init_db, AsyncSessionLocal, create_job, JobRow, update_job_status, save_json_field, get_job
from engine.researcher import run_research, _extract_internal_links, _extract_findings, _adapt_gemini_response, _normalise_scoring_fields, _SCORING_FIELDS, EvidenceLabel, Finding
from engine.web_utils import web_search, fetch_page
from scoring.engine import score
from engine.brief_generator import generate_brief, _extract_company_name, _call_llm_with_retry, _build_brief, _validate_no_label_upgrade
from knowledge.retrieval import retrieve_batch, format_chunks_for_prompt
from api.crm_adapter import MockHubSpotAdapter

COMPANIES = [
    {
        "scenario": "Scenario 1: Clear strong-fit façade/construction contractor",
        "company_name": "Eden Facades Ltd",
        "website": "https://www.edenfacades.co.uk",
    },
    {
        "scenario": "Scenario 2: Large non-construction company outside ICP",
        "company_name": "Spotify",
        "website": "https://www.spotify.com",
    },
    {
        "scenario": "Scenario 3: Small/lesser-known company with modest website",
        "company_name": "Concept Facades Ltd",
        "website": "https://www.conceptfacades.co.uk",
    },
    {
        "scenario": "Scenario 4: Minimal/sparse web presence contractor",
        "company_name": "Harts Roofing",
        "website": "https://www.hartsroofing.co.uk",
    },
]

async def profile_company(comp):
    req = ProspectRequest(company_name=comp["company_name"], website=comp["website"])
    company = comp["company_name"]
    website = comp["website"]
    
    print(f"\n=======================================================")
    print(f"Profiling: {company} ({website})")
    print(f"Scenario: {comp['scenario']}")
    print(f"=======================================================")
    
    t_start = time.perf_counter()
    timings = {}
    
    # -------------------------------------------------------------
    # 1. Web Search (Tavily)
    # -------------------------------------------------------------
    t_search_start = time.perf_counter()
    from urllib.parse import urlparse
    domain = urlparse(website).netloc or website.replace("https://", "").replace("http://", "").split("/")[0]
    search_queries = [
        f'"{company}" {domain} facade cladding curtain wall roofing contractor services about',
        f'"{company}" projects tenders case studies commercial residential',
        f'"{company}" leadership team directors estimating commercial director',
    ]
    search_tasks = [web_search(q, num_results=5) for q in search_queries]
    search_results_lists = await asyncio.gather(*search_tasks, return_exceptions=True)
    t_search_end = time.perf_counter()
    timings["search_tavily_s"] = round(t_search_end - t_search_start, 3)
    
    search_results = []
    for res in search_results_lists:
        if isinstance(res, list):
            search_results.extend(res)
    seen_urls = set()
    unique_results = []
    for r in search_results:
        link = r.get("link", "")
        if link and link not in seen_urls:
            seen_urls.add(link)
            unique_results.append(r)
            
    print(f"  [1] Web Search: {timings['search_tavily_s']}s ({len(unique_results)} search hits)")
    
    # -------------------------------------------------------------
    # 2. Web Crawling / Page Fetching
    # -------------------------------------------------------------
    t_crawl_start = time.perf_counter()
    homepage_text = await fetch_page(website, timeout=2.0)
    fetched_pages = []
    urls_to_fetch = []
    if homepage_text.strip():
        fetched_pages.append({"url": website, "text": homepage_text})
        internal_links = _extract_internal_links(homepage_text, domain)
        for link in internal_links:
            if link != website and link not in urls_to_fetch:
                urls_to_fetch.append(link)
    for r in unique_results:
        link = r.get("link", "")
        if link and link != website and link not in urls_to_fetch:
            urls_to_fetch.append(link)
        if len(urls_to_fetch) + len(fetched_pages) >= 8:
            break
    remaining_slots = 8 - len(fetched_pages)
    urls_to_fetch = urls_to_fetch[:remaining_slots]
    if urls_to_fetch:
        fetch_tasks = [fetch_page(u, timeout=2.0) for u in urls_to_fetch]
        fetched_texts = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        for u, res in zip(urls_to_fetch, fetched_texts):
            if isinstance(res, str) and res.strip():
                fetched_pages.append({"url": u, "text": res})
    t_crawl_end = time.perf_counter()
    timings["page_crawling_s"] = round(t_crawl_end - t_crawl_start, 3)
    print(f"  [2] Page Crawling: {timings['page_crawling_s']}s ({len(fetched_pages)} pages fetched)")
    
    # -------------------------------------------------------------
    # 3. LLM Extraction (Gemini)
    # -------------------------------------------------------------
    t_llm_ext_start = time.perf_counter()
    findings_raw = await _extract_findings(company, website, fetched_pages, unique_results)
    findings_raw = _adapt_gemini_response(findings_raw)
    t_llm_ext_end = time.perf_counter()
    timings["llm_extraction_s"] = round(t_llm_ext_end - t_llm_ext_start, 3)
    print(f"  [3] LLM Extraction: {timings['llm_extraction_s']}s")
    
    # Findings conversion
    from datetime import date
    today = date.today()
    all_fetched_urls = [p["url"] for p in fetched_pages]
    fallback_urls = [r.get("link", "") for r in unique_results[:5] if r.get("link")]
    for findings_list in [findings_raw.get("company_snapshot", []), 
                          findings_raw.get("decision_makers", []),
                          findings_raw.get("projects_signals", [])]:
        for finding in findings_list:
            if isinstance(finding, dict):
                existing_urls = finding.get("source_urls", [])
                if not existing_urls:
                    source_urls = all_fetched_urls if all_fetched_urls else fallback_urls
                    if source_urls:
                        finding["source_urls"] = source_urls[:1]
    
    from api.models import SourceRef
    def _parse_f(raw_list):
        out = []
        for item in raw_list:
            sources = [SourceRef(url=u, date_reviewed=today) for u in item.get("source_urls", []) if u]
            try:
                label = EvidenceLabel(item.get("label", "Unverified"))
            except Exception:
                label = EvidenceLabel.UNVERIFIED
            out.append(Finding(field=item.get("field", "unknown"), value=item.get("value", ""), label=label, sources=sources))
        return out
    
    company_snapshot = _normalise_scoring_fields(_parse_f(findings_raw.get("company_snapshot", [])))
    decision_makers = _parse_f(findings_raw.get("decision_makers", []))
    projects_signals = _normalise_scoring_fields(_parse_f(findings_raw.get("projects_signals", [])))
    notes_missing = findings_raw.get("notes_missing", [])
    
    existing_fields = {f.field for f in company_snapshot}
    for sf in _SCORING_FIELDS:
        if sf not in existing_fields:
            notes_missing.append(f"no evidence found for scoring field: {sf}")
            company_snapshot.append(Finding(field=sf, value="no evidence found", label=EvidenceLabel.UNVERIFIED, sources=[]))
            
    from api.models import ResearchFindings
    findings = ResearchFindings(
        job_id="profiling-job",
        company_snapshot=company_snapshot,
        decision_makers=decision_makers,
        projects_signals=projects_signals,
        notes_missing=notes_missing
    )
    
    t_research_total = time.perf_counter() - t_start
    timings["total_research_stage_s"] = round(t_research_total, 3)
    
    # -------------------------------------------------------------
    # 4. Deterministic Scoring
    # -------------------------------------------------------------
    t_score_start = time.perf_counter()
    lead_score = score(findings)
    t_score_end = time.perf_counter()
    timings["scoring_s"] = round(t_score_end - t_score_start, 4)
    print(f"  [4] Scoring: {timings['scoring_s']}s -> Score: {lead_score.total}/100 ({lead_score.band})")
    
    # -------------------------------------------------------------
    # 5. RAG Retrieval (Gemini Embeddings + ChromaDB)
    # -------------------------------------------------------------
    t_rag_start = time.perf_counter()
    cname = _extract_company_name(findings)
    kb_queries = [
        "Coextend services facade cladding estimating BIM shop drawings",
        "Coextend ideal customer profile ICP criteria",
        f"recommended approach outreach for {cname}",
        "Coextend capabilities positioning outsourcing value proposition",
    ]
    unique_chunks = await retrieve_batch(kb_queries, top_k=3)
    kb_text = format_chunks_for_prompt(unique_chunks[:10])
    t_rag_end = time.perf_counter()
    timings["rag_retrieval_s"] = round(t_rag_end - t_rag_start, 3)
    print(f"  [5] RAG Retrieval: {timings['rag_retrieval_s']}s ({len(unique_chunks)} chunks)")
    
    # -------------------------------------------------------------
    # 6. LLM Brief Generation (Gemini)
    # -------------------------------------------------------------
    t_brief_llm_start = time.perf_counter()
    findings_json = findings.model_dump_json(indent=2)
    score_json = lead_score.model_dump_json(indent=2)
    user_content = (
        f"INPUT A — Research Findings:\n{findings_json}\n\n"
        f"INPUT B — Lead Score:\n{score_json}\n\n"
        f"INPUT C — Internal Knowledge (cite source document names):\n{kb_text}"
    )
    raw_brief = await _call_llm_with_retry(user_content)
    brief = _build_brief(findings, lead_score, raw_brief, unique_chunks)
    _validate_no_label_upgrade(findings, brief)
    t_brief_llm_end = time.perf_counter()
    timings["llm_brief_generation_s"] = round(t_brief_llm_end - t_brief_llm_start, 3)
    print(f"  [6] LLM Brief Generation: {timings['llm_brief_generation_s']}s")
    
    # -------------------------------------------------------------
    # 7. CRM Export
    # -------------------------------------------------------------
    t_crm_start = time.perf_counter()
    crm = await MockHubSpotAdapter().export(brief)
    t_crm_end = time.perf_counter()
    timings["crm_export_s"] = round(t_crm_end - t_crm_start, 4)
    
    total_wall_clock = time.perf_counter() - t_start
    timings["total_wall_clock_s"] = round(total_wall_clock, 3)
    print(f"  TOTAL Wall-Clock: {timings['total_wall_clock_s']}s")
    
    return {
        "company_name": company,
        "website": website,
        "scenario": comp["scenario"],
        "timings": timings,
        "lead_score": {
            "total": lead_score.total,
            "band": lead_score.band,
            "breakdown": [f.model_dump() for f in lead_score.breakdown]
        },
        "snapshot": brief.snapshot,
        "contact": brief.contact,
        "recommended_approach": brief.recommended_approach.model_dump(),
        "num_sources": len(brief.sources),
        "sources": [str(s.url) for s in brief.sources]
    }

async def main():
    await init_db()
    from knowledge.retrieval import warm_embed_cache
    await warm_embed_cache()
    all_results = []
    for comp in COMPANIES:
        res = await profile_company(comp)
        all_results.append(res)
        await asyncio.sleep(1.0)  # Gentle pause between companies to respect free-tier quotas
        
    with open("optimized_profiling_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\n\nAll 4 companies profiled successfully. Saved to optimized_profiling_results.json")

if __name__ == "__main__":
    asyncio.run(main())
