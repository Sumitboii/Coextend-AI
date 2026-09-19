#!/usr/bin/env python3
"""
Test script to verify the research depth fix.
Tests with Enclos Corp and Permasteelisa International.
"""
import asyncio
import json
from datetime import date
from api.models import ProspectRequest, ResearchFindings
from engine.researcher import run_research

async def test_research_depth():
    """Test the research depth fix with two companies."""
    
    test_cases = [
        {
            "company": "Enclos Corp",
            "website": "https://www.enclos.com",
        },
        {
            "company": "Permasteelisa International",
            "website": "https://www.permasteelisa.com",
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*80}")
        print(f"Testing: {test['company']}")
        print(f"Website: {test['website']}")
        print(f"{'='*80}\n")
        
        try:
            req = ProspectRequest(
                company_name=test["company"],
                website=test["website"]
            )
            
            job_id = f"test-{test['company'].replace(' ', '_')}"
            findings = await run_research(job_id, req)
            
            # Extract statistics
            snapshot_count = len(findings.company_snapshot)
            dm_count = len(findings.decision_makers)
            signals_count = len(findings.projects_signals)
            missing_count = len(findings.notes_missing)
            
            # Extract unique sources
            all_sources = set()
            for f in findings.company_snapshot + findings.decision_makers + findings.projects_signals:
                for src in f.sources:
                    all_sources.add(src.url)
            
            print(f"Company Snapshot entries: {snapshot_count}")
            print(f"Decision Makers entries: {dm_count}")
            print(f"Projects/Signals entries: {signals_count}")
            print(f"Unique sources retrieved: {len(all_sources)}")
            print(f"Missing evidence notes: {missing_count}")
            
            # Check key fields
            snapshot_fields = {f.field for f in findings.company_snapshot}
            key_scoring_fields = [
                'trade_fit', 'geography', 'company_size_band', 'tender_volume_signal',
                'estimating_need_signal', 'drafting_bim_need_signal', 'hiring_trigger',
                'decision_maker_access', 'outsourcing_readiness', 'commercial_attractiveness'
            ]
            
            populated_fields = {f for f in key_scoring_fields if f in snapshot_fields}
            print(f"\nKey scoring fields populated: {len(populated_fields)}/{len(key_scoring_fields)}")
            for field in key_scoring_fields:
                if field in snapshot_fields:
                    values = [f.value for f in findings.company_snapshot if f.field == field]
                    print(f"  ✓ {field}: {values[0][:60]}..." if len(values[0]) > 60 else f"  ✓ {field}: {values[0]}")
                else:
                    print(f"  ✗ {field}: NOT FOUND")
            
            # Print sample sources
            print(f"\nSample sources retrieved:")
            for i, src in enumerate(sorted(all_sources)[:5], 1):
                print(f"  {i}. {src}")
            if len(all_sources) > 5:
                print(f"  ... and {len(all_sources) - 5} more")
            
            print("\n" + "="*80)
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_research_depth())
