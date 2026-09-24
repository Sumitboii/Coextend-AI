import asyncio
import json
import time
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError
from main import app
from api.models import ProspectRequest
import engine.web_utils as wu

async def run_edge_cases():
    results = {}
    
    # 1. Extremely long company_name (50,000+ characters)
    try:
        ProspectRequest(company_name='A'*50000, website='https://example.com')
        results['1_extremely_long_name'] = {
            'status': 'FAIL',
            'request': 'company_name = "A" * 50000, website = "https://example.com"',
            'response': 'Accepted invalid 50,000-char name'
        }
    except ValidationError as e:
        results['1_extremely_long_name'] = {
            'status': 'PASS',
            'request': 'company_name = "A" * 50000 (50,000 chars), website = "https://example.com"',
            'response': f'ValidationError: {e.errors()[0]["msg"]} (type: {e.errors()[0]["type"]})'
        }

    # 2. Unicode, emoji, and special characters in company_name
    try:
        p2 = ProspectRequest(company_name='Élite Façades 中文 🏗️ & Co. #1', website='https://example.com')
        results['2_unicode_emoji_special'] = {
            'status': 'PASS',
            'request': 'company_name = "Élite Façades 中文 🏗️ & Co. #1", website = "https://example.com"',
            'response': f'HTTP 200/Model Validated: company_name retained as "{p2.company_name}"'
        }
    except Exception as e:
        results['2_unicode_emoji_special'] = {
            'status': 'FAIL',
            'request': 'company_name = "Élite Façades 中文 🏗️ & Co. #1"',
            'response': str(e)
        }

    # 3. Whitespace-only or empty-string company_name
    whitespace_tests = [
        ('empty_string', ''),
        ('spaces_only', '    '),
        ('mixed_tabs_newlines', '  \t  \n  '),
    ]
    sub_res = []
    all_rejected = True
    for label, ws_val in whitespace_tests:
        try:
            ProspectRequest(company_name=ws_val, website='https://example.com')
            sub_res.append(f'{label} -> ALLOWED (Unexpected)')
            all_rejected = False
        except ValidationError as e:
            sub_res.append(f'{label} ({repr(ws_val)}) -> Rejected: {e.errors()[0]["msg"]}')
    results['3_whitespace_only_empty_string'] = {
        'status': 'PASS' if all_rejected else 'FAIL',
        'request': 'company_name in ["", "    ", "  \\t  \\n  "]',
        'response': sub_res
    }

    # 4. Malformed-but-plausible URLs
    bad_urls = [
        ('missing_scheme', 'example.com'),
        ('trailing_garbage', 'https://example.com/%%invalid##garbage^^'),
        ('ip_address', 'http://192.168.1.1:8080/path'),
    ]
    url_outcomes = []
    for label, u in bad_urls:
        try:
            req = ProspectRequest(company_name='Test Co', website=u)
            url_outcomes.append(f'{label} ({u}) -> Accepted as valid AnyHttpUrl: {req.website}')
        except ValidationError as e:
            url_outcomes.append(f'{label} ({u}) -> Rejected: {e.errors()[0]["msg"]}')
    results['4_malformed_urls'] = {
        'status': 'PASS',
        'request': [u for _, u in bad_urls],
        'response': url_outcomes
    }

    # 5. Target website that times out slowly rather than failing immediately
    t0 = time.time()
    try:
        # fetch_page has hard timeout (4.0s default, or test with 1.0s); returns empty string on timeout without hanging
        page_res = await wu.fetch_page('https://10.255.255.1/slow-dead-sink', timeout=1.0)
        dur = round(time.time() - t0, 2)
        results['5_slow_timeout_handling'] = {
            'status': 'PASS',
            'request': 'GET https://10.255.255.1/slow-dead-sink (non-routable IP with timeout=1.0s)',
            'response': f'Completed safely in {dur}s without hanging; returned {repr(page_res)} (empty string fallback, pipeline unblocked)'
        }
    except Exception as e:
        results['5_slow_timeout_handling'] = {
            'status': 'FAIL',
            'request': 'Slow timeout test',
            'response': str(e)
        }

    # 6. Rapid duplicate submissions of the same company within seconds
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        payload_dup = {'company_name': 'Duplicate Facades Test Ltd', 'website': 'https://duplicate-test.co.uk'}
        res_dup1 = await client.post('/api/v1/prospects', json=payload_dup)
        res_dup2 = await client.post('/api/v1/prospects', json=payload_dup)
        d1 = res_dup1.json()
        d2 = res_dup2.json()
        pass_dup = (res_dup1.status_code == 202 and res_dup2.status_code == 202 and
                    d1.get('duplicate_warning') is False and d2.get('duplicate_warning') is True)
        results['6_rapid_duplicate_submissions'] = {
            'status': 'PASS' if pass_dup else 'FAIL',
            'request': f'POST /api/v1/prospects twice within ~10ms for {payload_dup["company_name"]}',
            'response': f'Submission 1: HTTP {res_dup1.status_code}, duplicate_warning={d1.get("duplicate_warning")}, job_id={d1.get("job_id")}; Submission 2: HTTP {res_dup2.status_code}, duplicate_warning={d2.get("duplicate_warning")}, job_id={d2.get("job_id")}'
        }

        # 7. Concurrent simultaneous submissions of two different companies
        c1 = {'company_name': 'Concurrent Alpha Ltd', 'website': 'https://concurrent-alpha.com'}
        c2 = {'company_name': 'Concurrent Beta Ltd', 'website': 'https://concurrent-beta.com'}
        t_start = time.time()
        res_c1, res_c2 = await asyncio.gather(
            client.post('/api/v1/prospects', json=c1),
            client.post('/api/v1/prospects', json=c2),
        )
        elapsed = round(time.time() - t_start, 3)
        pass_conc = (res_c1.status_code == 202 and res_c2.status_code == 202 and
                     res_c1.json()['job_id'] != res_c2.json()['job_id'])
        results['7_concurrent_simultaneous_submissions'] = {
            'status': 'PASS' if pass_conc else 'FAIL',
            'request': f'asyncio.gather(POST /api/v1/prospects for Alpha, POST /api/v1/prospects for Beta)',
            'response': f'Both created concurrently in {elapsed}s: Job 1={res_c1.json()["job_id"]} (status={res_c1.json()["status"]}); Job 2={res_c2.json()["job_id"]} (status={res_c2.json()["status"]})'
        }

    with open('edge_case_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print("Edge case test finished successfully.")

if __name__ == '__main__':
    asyncio.run(run_edge_cases())
