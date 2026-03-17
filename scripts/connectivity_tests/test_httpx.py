import httpx

try:
    print("Testing httpx default...")
    resp = httpx.get("https://generativelanguage.googleapis.com", timeout=10)
    print("Status:", resp.status_code)
except Exception as e:
    print("Default failed:", type(e).__name__, e)
