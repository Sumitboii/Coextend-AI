import re
from urllib.parse import urljoin, urlparse

def _extract_internal_links(page_text, domain):
    links = re.findall(r"href=[\"']([^\"']+)[\"']", page_text)
    internal = []
    keywords = ["project", "case", "portfolio", "work", "about", "team", "services", "news", "press", "blog", "capability", "solution", "award"]
    
    for link in links:
        try:
            full_url = urljoin("https://" + domain, link)
            if urlparse(full_url).netloc == domain and any(k in full_url.lower() for k in keywords):
                internal.append(full_url)
        except:
            pass
    
    return list(set(internal))[:8]

test_links = [
    "/projects",
    "/portfolio",
    "/about",
    "/team",
    "/news",
    "/case-studies",
    "https://enclos.com/work",
]

domain = "enclos.com"
for link in test_links:
    full = urljoin("https://" + domain, link)
    netloc_ok = urlparse(full).netloc == domain
    has_keyword = any(k in full.lower() for k in ["project", "case", "portfolio", "work", "about", "team", "services", "news", "press", "blog", "capability", "solution", "award"])
    print(f"{link} -> {full}")
    print(f"  netloc_ok={netloc_ok}, has_keyword={has_keyword}, INCLUDE={netloc_ok and has_keyword}")
