import time
from config import settings
from google import genai
from tavily import TavilyClient

print(f"Testing Gemini Client with model: {settings.gemini_llm_model}")
client = genai.Client(api_key=settings.gemini_api_key)

t0 = time.time()
try:
    resp = client.models.generate_content(
        model=settings.gemini_llm_model,
        contents="Say hello in one word",
    )
    t1 = time.time()
    print(f"Gemini success in {t1 - t0:.2f}s: {resp.text.strip()}")
except Exception as e:
    print(f"Gemini Error: {e}")

print("\nTesting Tavily Client...")
tav_client = TavilyClient(api_key=settings.tavily_api_key)
t0 = time.time()
try:
    res = tav_client.search(query="Apex Facades UK", max_results=3)
    t1 = time.time()
    print(f"Tavily success in {t1 - t0:.2f}s: {len(res.get('results', []))} results")
except Exception as e:
    print(f"Tavily Error: {e}")
