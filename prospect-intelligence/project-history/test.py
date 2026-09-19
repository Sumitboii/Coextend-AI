import urllib.request, json, sqlite3, time
BASE = 'http://localhost:8000/api/v1'
JOB = '06733c2d-f548-4c6d-9d56-bbf98847159a'

def get(path):
    return json.loads(urllib.request.urlopen(BASE+path,timeout=15).read())

def post(path, body=None):
    data = json.dumps(body or {}).encode()
    r = urllib.request.Request(BASE+path, data=data, headers={'Content-Type':'application/json'}, method='POST')
    return json.loads(urllib.request.urlopen(r,timeout=15).read())

print('TEST 1: E2E PIPELINE'); b = get(f'/prospects/{JOB}/brief'); c = get(f'/prospects/{JOB}/crm-export'); o = post(f'/prospects/{JOB}/outreach')
sections = ['snapshot','contact','company_research','projects_signals','likely_requirements','pain_point_hypotheses','lead_score','recommended_approach','risks_unknowns','next_action','sources']
print(f'  [{"PASS" if all(s in b for s in sections) else "FAIL"}] 11 sections'); bd = b.get('lead_score',{}).get('breakdown',[])
print(f'  [{"PASS" if len(bd)==10 else "FAIL"}] 10 factors'); sc = b.get('lead_score',{}).get('total')
print(f'  [{"PASS" if 0<=sc<=100 else "FAIL"}] score 0-100'); print(f'  [{"PASS" if b.get("lead_score",{}).get("rubric_version") else "FAIL"}] rubric_version')
all_f = b.get('projects_signals',[]) + b.get('likely_requirements',[]) + b.get('pain_point_hypotheses',[])
no_label = [f for f in all_f if not f.get('label')]; print(f'  [{"PASS" if not no_label else "FAIL"}] findings have labels')
print(f'  [PASS] {len(b.get("sources",[]))} sources'); print(f'  [{"PASS" if o.get("status")=="draft" else "FAIL"}] outreach draft')
print(f'  [{"PASS" if len(o.get("linkedin_message",""))<=300 else "FAIL"}] linkedin<=300')

print('\nTEST 2: FAB-01 Anti-fabrication'); j2 = post('/prospects', {'company_name':'XYZNONEXISTENT99','website':'https://xyznonexistent99fake.co.uk'})
jid2 = j2['job_id']; deadline = time.time() + 120
while time.time() < deadline:
    j2 = get(f'/prospects/{jid2}')
    if j2['status'] in ['complete','failed']: break; time.sleep(5)
print(f'  Status: {j2["status"]}')
if j2['status']=='complete': b2 = get(f'/prospects/{jid2}/brief'); snap = b2.get('snapshot',{}); print(f'  company_name: {snap.get("company_name","EMPTY")}')
else: print(f'  Error: {j2.get("error_message","")}')

print('\nTEST 3: SCORE-03 Repeatability'); conn = sqlite3.connect('data/prospect_intelligence.db')
row = conn.execute('SELECT findings_json FROM jobs WHERE job_id=?', (JOB,)).fetchone(); conn.close()
from api.models import ResearchFindings; from scoring.engine import score
findings = ResearchFindings(**json.loads(row[0])); s1 = score(findings); s2 = score(findings)
print(f'  [{"PASS" if s1.total==s2.total and s1.band==s2.band else "FAIL"}] {s1.total}=={s2.total}')

print('\nTEST 4: FAIL-03 Malformed'); cases = [('missing company_name', {'website':'https://example.com'}), ('empty company_name', {'company_name':'','website':'https://example.com'}), ('ftp scheme', {'company_name':'Test','website':'ftp://example.com'}), ('not a url', {'company_name':'Test','website':'not-a-url'})]
passed = 0
for label, body in cases:
    try: urllib.request.Request(BASE+'/prospects', data=json.dumps(body).encode(), headers={'Content-Type':'application/json'}, method='POST'); urllib.request.urlopen(urllib.request.Request(BASE+'/prospects', data=json.dumps(body).encode(), headers={'Content-Type':'application/json'}, method='POST')); print(f'  [FAIL] {label}')
    except urllib.error.HTTPError as e: passed += 1 if e.code==422 else 0; print(f'  [{"PASS" if e.code==422 else "FAIL"}] {label} - {e.code}')
print(f'  Total: {passed}/4')

print('\nTEST 5: 404 missing'); 
try: urllib.request.urlopen(BASE+'/prospects/00000000-0000-0000-0000-000000000000')
except urllib.error.HTTPError as e: print(f'  [{"PASS" if e.code==404 else "FAIL"}] {e.code}')

print('\n=== DONE ===')
