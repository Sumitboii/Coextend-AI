import asyncio
import json
from httpx import AsyncClient, ASGITransport
from main import app

async def run_fuzzing():
    results = {}
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Wrong data type for a field (e.g. company_name as a number, or an array)
        req_1a = {"company_name": 12345, "website": "https://example.com"} # number
        res_1a = await client.post("/api/v1/prospects", json=req_1a)
        
        req_1b = {"company_name": ["Acme", "Corp"], "website": "https://example.com"} # array
        res_1b = await client.post("/api/v1/prospects", json=req_1b)
        
        results["1_wrong_data_type"] = {
            "cases": [
                {
                    "description": "company_name as number (12345)",
                    "request_body": req_1a,
                    "status_code": res_1a.status_code,
                    "response_body": res_1a.json()
                },
                {
                    "description": "company_name as array (['Acme', 'Corp'])",
                    "request_body": req_1b,
                    "status_code": res_1b.status_code,
                    "response_body": res_1b.json()
                }
            ]
        }

        # 2. Extra/unexpected fields included in the body
        req_2 = {
            "company_name": "Acme Façades Ltd",
            "website": "https://acme.com",
            "unexpected_field": "injected_payload_data",
            "context_notes": "legacy extra note",
            "hack_param": 9999
        }
        res_2 = await client.post("/api/v1/prospects", json=req_2)
        results["2_extra_unexpected_fields"] = {
            "description": "Extra unexpected fields included in JSON body (extra='ignore' in Pydantic)",
            "request_body": req_2,
            "status_code": res_2.status_code,
            "response_body": res_2.json(),
            "notes": "Extra fields are safely stripped; job created cleanly without error"
        }

        # 3. Required field explicitly set to null vs. omitted entirely vs. empty string
        # company_name
        req_3_null = {"company_name": None, "website": "https://example.com"}
        res_3_null = await client.post("/api/v1/prospects", json=req_3_null)

        req_3_omitted = {"website": "https://example.com"}
        res_3_omitted = await client.post("/api/v1/prospects", json=req_3_omitted)

        req_3_empty = {"company_name": "", "website": "https://example.com"}
        res_3_empty = await client.post("/api/v1/prospects", json=req_3_empty)

        # website
        req_3_web_null = {"company_name": "Acme", "website": None}
        res_3_web_null = await client.post("/api/v1/prospects", json=req_3_web_null)

        results["3_null_vs_omitted_vs_empty"] = {
            "cases": [
                {
                    "description": "company_name explicitly null",
                    "request_body": req_3_null,
                    "status_code": res_3_null.status_code,
                    "response_body": res_3_null.json()
                },
                {
                    "description": "company_name omitted entirely",
                    "request_body": req_3_omitted,
                    "status_code": res_3_omitted.status_code,
                    "response_body": res_3_omitted.json()
                },
                {
                    "description": "company_name empty string",
                    "request_body": req_3_empty,
                    "status_code": res_3_empty.status_code,
                    "response_body": res_3_empty.json()
                },
                {
                    "description": "website explicitly null",
                    "request_body": req_3_web_null,
                    "status_code": res_3_web_null.status_code,
                    "response_body": res_3_web_null.json()
                }
            ]
        }

        # 4. An empty JSON body {}
        req_4 = {}
        res_4 = await client.post("/api/v1/prospects", json=req_4)
        results["4_empty_json_body"] = {
            "description": "Empty JSON object {}",
            "request_body": req_4,
            "status_code": res_4.status_code,
            "response_body": res_4.json()
        }

        # 5. A deeply nested object where a plain string is expected
        req_5 = {
            "company_name": {
                "deeply": {
                    "nested": {
                        "name": "Acme Deep"
                    }
                }
            },
            "website": "https://example.com"
        }
        res_5 = await client.post("/api/v1/prospects", json=req_5)
        results["5_deeply_nested_object"] = {
            "description": "company_name passed as deeply nested JSON object",
            "request_body": req_5,
            "status_code": res_5.status_code,
            "response_body": res_5.json()
        }

        # 6. Wrong Content-Type header (e.g. text/plain instead of application/json)
        req_6_body = '{"company_name": "Acme", "website": "https://example.com"}'
        res_6 = await client.post(
            "/api/v1/prospects",
            content=req_6_body,
            headers={"Content-Type": "text/plain"}
        )
        try:
            res_6_json = res_6.json()
        except Exception:
            res_6_json = res_6.text
        results["6_wrong_content_type"] = {
            "description": "POST with Content-Type: text/plain",
            "request_headers": {"Content-Type": "text/plain"},
            "request_content": req_6_body,
            "status_code": res_6.status_code,
            "response_body": res_6_json
        }

        # 7. Duplicate JSON keys in the same payload
        # When raw JSON with duplicate keys is parsed by FastAPI/Starlette, standard JSON deserialization semantics apply
        raw_dup_json = '{"company_name": "First Name", "company_name": "Second Name", "website": "https://example.com"}'
        res_7 = await client.post(
            "/api/v1/prospects",
            content=raw_dup_json,
            headers={"Content-Type": "application/json"}
        )
        results["7_duplicate_json_keys"] = {
            "description": "Payload with duplicate 'company_name' keys",
            "raw_payload": raw_dup_json,
            "status_code": res_7.status_code,
            "response_body": res_7.json()
        }

    with open("payload_fuzzing_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Payload fuzzing complete.")

if __name__ == "__main__":
    asyncio.run(run_fuzzing())
