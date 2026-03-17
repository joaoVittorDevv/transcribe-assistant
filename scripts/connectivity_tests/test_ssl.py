import httpx
import certifi
import ssl

print("Testing httpx with default Context...")
try:
    with httpx.Client() as c:
        resp = c.get("https://generativelanguage.googleapis.com", timeout=10)
        print("Default Status:", resp.status_code)
except Exception as e:
    print("Default failed:", type(e).__name__, e)

print("Testing httpx with certifi Context...")
try:
    ctx = ssl.create_default_context(cafile=certifi.where())
    with httpx.Client(verify=ctx) as c:
        resp = c.get("https://generativelanguage.googleapis.com", timeout=10)
        print("Certifi Status:", resp.status_code)
except Exception as e:
    print("Certifi failed:", type(e).__name__, e)
