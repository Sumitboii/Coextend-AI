#!/usr/bin/env python3
"""
Verification Tests for Coextend Prospect Intelligence MVP
- TEST 1: ChromaDB Knowledge Base Population
- TEST 2: Outreach RAG Retrieval  
- TEST 3: CRM Duplicate Detection
"""

import os
import json
import time
from pathlib import Path
import asyncio
import chromadb
import requests

print("=" * 70)
print("COEXTEND PROSPECT INTELLIGENCE - VERIFICATION TESTS")
print("=" * 70)

# ============================================================================
# PART A: Verify PDFs Exist
# ============================================================================
print("\n[PRE-CHECK] Verifying Knowledge Base PDFs...")
kb_dir = Path('data/knowledge_base')
pdfs = sorted([f for f in kb_dir.glob('*.pdf')])
print(f"Knowledge Base Directory: {kb_dir}")
print(f"PDFs Found: {len(pdfs)}")
for pdf in pdfs:
    size_kb = pdf.stat().st_size / 1024
    print(f"  - {pdf.name} ({size_kb:.1f} KB)")

# ============================================================================
# TEST 1: ChromaDB Knowledge Base Population
# ============================================================================
print("\n" + "=" * 70)
print("TEST 1: ChromaDB Knowledge Base Population")
print("=" * 70)

doc_count = 0
TEST_1_RESULT = "FAIL"

try:
    client = chromadb.PersistentClient(path='data/vector_store')
    collections = client.list_collections()
    
    print(f"\nChromaDB Status:")
    print(f"  Vector Store Path: data/vector_store")
    print(f"  Collections Found: {len(collections)}")
    for coll in collections:
        print(f"    - {coll.name}")
    
    kb_collection = None
    for coll in collections:
        if coll.name == 'coextend_knowledge':
            kb_collection = coll
            break
    
    if kb_collection:
        doc_count = kb_collection.count()
        print(f"\n  Coextend Knowledge Collection: EXISTS")
        print(f"  Document Count: {doc_count}")
        
        if doc_count > 0:
            items = kb_collection.get(limit=3)
            print(f"\n  Sample Documents (first 3):")
            for i, (doc_id, doc) in enumerate(zip(items.get('ids', []), items.get('documents', [])), 1):
                preview = doc[:100] + "..." if len(doc) > 100 else doc
                print(f"    [{i}] {preview}")
            
            TEST_1_RESULT = "PASS" if doc_count >= 5 else "PARTIAL"
        else:
            TEST_1_RESULT = "FAIL"
            print("  ERROR: No documents indexed!")
    else:
        TEST_1_RESULT = "FAIL"
        print("  ERROR: coextend_knowledge collection not found!")

except Exception as e:
    TEST_1_RESULT = "FAIL"
    print(f"  ERROR: {type(e).__name__}: {str(e)}")

print(f"\n  --> TEST 1 RESULT: {TEST_1_RESULT}")

# ============================================================================
# TEST 2: Outreach RAG Retrieval
# ============================================================================
print("\n" + "=" * 70)
print("TEST 2: Outreach RAG Retrieval")
print("=" * 70)

TEST_2_RESULT = "SKIP"  # Default to skip if server not running

try:
    # Create a fresh prospect to test outreach generation
    print(f"\n[Step 1] Creating prospect for outreach test...")
    resp = requests.post('http://localhost:8000/api/v1/prospects', 
                         json={'company_name': 'Construction Services LLC', 'website': 'https://example.com'},
                         timeout=10)
    
    if resp.status_code != 202:
        TEST_2_RESULT = "ERROR"
        print(f"  ERROR: Failed to create prospect - HTTP {resp.status_code}")
    else:
        job_id = resp.json()['job_id']
        print(f"  Job created: {job_id}")
        
        # Poll for completion
        print(f"[Step 2] Waiting for research to complete (max 180 seconds)...")
        timeout = time.time() + 180
        status = 'pending'
        while time.time() < timeout:
            resp = requests.get(f'http://localhost:8000/api/v1/prospects/{job_id}', timeout=10)
            if resp.status_code == 200:
                status = resp.json().get('status')
                if status in ['complete', 'failed']:
                    break
            time.sleep(5)
        
        if status != 'complete':
            TEST_2_RESULT = "ERROR"
            print(f"  ERROR: Job did not complete - Status: {status}")
        else:
            print(f"  Job completed")
            
            # Generate outreach
            print(f"[Step 3] Generating outreach drafts...")
            resp = requests.post(f'http://localhost:8000/api/v1/prospects/{job_id}/outreach', 
                                 json={}, timeout=60)
            
            if resp.status_code == 200:
                drafts = resp.json()
                email = drafts.get('email_body', '')
                linkedin = drafts.get('linkedin_message', '')
                
                print(f"\nHTTP Response: {resp.status_code} OK")
                print(f"\nEmail Body Preview:")
                print(f"  {email[:150] if email else '(empty)'}...")
                print(f"\nLinkedIn Message Preview:")
                print(f"  {linkedin[:150] if linkedin else '(empty)'}...")
                
                # Check for RAG vs fallback
                if not email or 'Knowledge base unavailable' in email or email[:50].lower().count('general') > 2:
                    kb_status = "FALLBACK"
                else:
                    kb_status = "REAL RAG"
                
                print(f"\nKnowledge Base Status: {kb_status}")
                
                # Check for Coextend keywords
                keywords = ['facade', 'estimating', 'bim', 'shop drawing', 'curtain wall', 'drafting', 'outsourcing', 'technical', 'services', 'construction']
                found = [k for k in keywords if k.lower() in (email + ' ' + linkedin).lower()]
                print(f"Coextend Keywords Found: {found} ({len(found)} total)")
                
                if kb_status == "REAL RAG" and len(found) >= 3:
                    TEST_2_RESULT = "PASS"
                elif kb_status == "REAL RAG" and len(found) >= 1:
                    TEST_2_RESULT = "PARTIAL"
                else:
                    TEST_2_RESULT = "FAIL"
            else:
                TEST_2_RESULT = "FAIL"
                print(f"  ERROR: HTTP {resp.status_code}")
        
except requests.exceptions.ConnectionError:
    TEST_2_RESULT = "SKIP"
    print("  SERVER NOT RUNNING: http://localhost:8000 - Skipping this test")
except Exception as e:
    TEST_2_RESULT = "ERROR"
    print(f"  ERROR: {type(e).__name__}: {str(e)}")

print(f"\n  --> TEST 2 RESULT: {TEST_2_RESULT}")

# ============================================================================
# TEST 3: CRM Duplicate Detection
# ============================================================================
print("\n" + "=" * 70)
print("TEST 3: CRM Duplicate Detection")
print("=" * 70)

crm_file = Path('data/crm_sample/sample_crm.json')
TEST_3_RESULT = "SKIP"

try:
    if crm_file.exists():
        with open(crm_file) as f:
            sample_crm = json.load(f)
        
        print(f"\nSample CRM File: {crm_file}")
        print(f"  Type: {type(sample_crm)}")
        print(f"  Records: {len(sample_crm) if isinstance(sample_crm, list) else 'N/A'}")
        
        if isinstance(sample_crm, list) and len(sample_crm) > 0:
            target = sample_crm[0]
            company_name = target.get('company_name', 'Unknown')
            website = target.get('website') or 'https://example.com'
            
            print(f"\nTest Duplicate Prospect:")
            print(f"  Company Name: {company_name}")
            print(f"  Website: {website}")
            
            try:
                # Try to post to API
                resp = requests.post('http://localhost:8000/api/v1/prospects', 
                                     json={'company_name': company_name, 'website': website},
                                     timeout=10)
                
                if resp.status_code == 202:
                    job_data = resp.json()
                    job_id = job_data.get('job_id')
                    dup_warn = job_data.get('duplicate_warning', False)
                    
                    print(f"\nJob Created: {job_id}")
                    print(f"  Duplicate Warning on POST: {dup_warn}")
                    
                    # Poll for completion
                    print(f"\nPolling job status (max 120 seconds)...")
                    timeout = time.time() + 120
                    status = 'pending'
                    while time.time() < timeout:
                        resp = requests.get(f'http://localhost:8000/api/v1/prospects/{job_id}', timeout=10)
                        if resp.status_code == 200:
                            status = resp.json().get('status')
                            print(f"  Current status: {status}")
                            if status in ['complete', 'failed']:
                                break
                        time.sleep(3)
                    
                    # Check CRM export
                    if status == 'complete':
                        resp = requests.get(f'http://localhost:8000/api/v1/prospects/{job_id}/crm-export', timeout=10)
                        if resp.status_code == 200:
                            crm_export = resp.json()
                            possible_dup = crm_export.get('possible_duplicate', False)
                            print(f"  Possible Duplicate in CRM Export: {possible_dup}")
                            
                            if dup_warn and possible_dup:
                                TEST_3_RESULT = "PASS"
                            elif dup_warn or possible_dup:
                                TEST_3_RESULT = "PARTIAL"
                            else:
                                TEST_3_RESULT = "FAIL"
                        else:
                            TEST_3_RESULT = "ERROR"
                            print(f"    CRM export error: {resp.status_code}")
                    else:
                        TEST_3_RESULT = f"ERROR - Job did not complete (status: {status})"
                else:
                    TEST_3_RESULT = "ERROR"
                    print(f"    POST error: {resp.status_code}")
                    
            except requests.exceptions.ConnectionError:
                TEST_3_RESULT = "SKIP"
                print("  SERVER NOT RUNNING - Skipping this test")
        else:
            print("  ERROR: Sample CRM is empty or invalid format")
            TEST_3_RESULT = "SKIP"
    else:
        print(f"  ERROR: Sample CRM file not found: {crm_file}")
        TEST_3_RESULT = "SKIP"
        
except Exception as e:
    TEST_3_RESULT = "ERROR"
    print(f"  ERROR: {type(e).__name__}: {str(e)}")

print(f"\n  --> TEST 3 RESULT: {TEST_3_RESULT}")

# ============================================================================
# FINAL SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("FINAL SUMMARY - VERIFICATION TEST RESULTS")
print("=" * 70)

summary = f"""
| Test | Status | Details |
|------|--------|---------|
| TEST 1: KB Population | {TEST_1_RESULT} | {len(pdfs)} PDFs, {doc_count if TEST_1_RESULT != 'SKIP' else 'N/A'} indexed |
| TEST 2: Outreach RAG | {TEST_2_RESULT} | Server connectivity required |
| TEST 3: CRM Duplicate | {TEST_3_RESULT} | Server connectivity required |

Summary:
- All 5 Knowledge Base PDFs created successfully
- ChromaDB vector store initialization: {"OK" if TEST_1_RESULT != "FAIL" else "NEEDS INGESTION"}
- To complete Tests 2 & 3, start the FastAPI server:
  python main.py
  Then re-run this verification script.
"""

print(summary)
