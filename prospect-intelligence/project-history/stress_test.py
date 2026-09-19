import requests, time, json, sys

companies = [
    ('Enclos Corp', 'https://www.enclos.com'),
    ('Permasteelisa', 'https://www.permasteelisa.com'),
    ('Berkley Roofing Company', 'https://www.berkleyroofing.com'),
    ('Turner Construction', 'https://www.turnerconstruction.com'),
    ('Mayo Clinic', 'https://www.mayoclinic.org'),
    ('Small Local Builders LLC', 'https://smalllocalbuilders.example')
]

results = []

for i, (company_name, website) in enumerate(companies, 1):
    print(f'\n{"="*70}', flush=True)
    print(f'[{i}/6] {company_name}', flush=True)
    
    try:
        resp = requests.post('http://localhost:8000/api/v1/prospects',
                            json={'company_name': company_name, 'website': website},
                            timeout=10)
        if resp.status_code != 202:
            print(f'POST failed: {resp.status_code}', flush=True)
            continue
        job_id = resp.json()['job_id']
        print(f'Job: {job_id}', flush=True)
    except Exception as e:
        print(f'POST error: {e}', flush=True)
        continue
    
    timeout = time.time() + 180
    status = 'pending'
    while time.time() < timeout:
        try:
            resp = requests.get(f'http://localhost:8000/api/v1/prospects/{job_id}', timeout=5)
            if resp.status_code == 200:
                status = resp.json()['status']
                if status in ['complete', 'failed']:
                    break
        except:
            pass
        time.sleep(3)
    
    if status != 'complete':
        print(f'Status: {status}', flush=True)
        continue
    
    print(f'Status: {status}', flush=True)
    
    try:
        brief_resp = requests.get(f'http://localhost:8000/api/v1/prospects/{job_id}/brief', timeout=5)
        crm_resp = requests.get(f'http://localhost:8000/api/v1/prospects/{job_id}/crm-export', timeout=5)
        outreach_resp = requests.post(f'http://localhost:8000/api/v1/prospects/{job_id}/outreach', json={}, timeout=10)
        
        brief = brief_resp.json() if brief_resp.status_code == 200 else {}
        crm = crm_resp.json() if crm_resp.status_code == 200 else {}
        outreach = outreach_resp.json() if outreach_resp.status_code == 200 else {}
        
        score = brief.get('lead_score', {}).get('total', 0)
        band = brief.get('lead_score', {}).get('band', 'N/A')
        
        print(f'Score: {score}/100 ({band})', flush=True)
        print(f'Projects: {len(brief.get("projects_signals", []))} items', flush=True)
        print(f'Sources: {len(brief.get("sources", []))} URLs', flush=True)
        
        results.append({
            'company': company_name,
            'website': website,
            'job_id': job_id,
            'score': score,
            'band': band,
            'snapshot': brief.get('snapshot', {}),
            'lead_score': brief.get('lead_score', {}),
            'projects_signals': brief.get('projects_signals', []),
            'likely_requirements': brief.get('likely_requirements', []),
            'pain_point_hypotheses': brief.get('pain_point_hypotheses', []),
            'sources': brief.get('sources', []),
            'crm_export': crm,
            'outreach': outreach
        })
        
        print('Success', flush=True)
    except Exception as e:
        print(f'Retrieve error: {e}', flush=True)

with open('real-world-test-results.json', 'w') as f:
    json.dump(results, f, indent=2, default=str)

print(f'\nCompleted: {len(results)}/6 companies')
print(f'Saved: real-world-test-results.json')
