import httpx
print("Testing HTTP/1.1...")
try:
    with httpx.Client(http2=False) as c:
        resp = c.get("https://generativelanguage.googleapis.com", timeout=10)
        print("HTTP/1.1 Status:", resp.status_code)
except Exception as e:
    print("HTTP/1.1 failed:", e)

print("Testing HTTP/2...")
try:
    with httpx.Client(http2=True) as c:
        resp = c.get("https://generativelanguage.googleapis.com", timeout=10)
        print("HTTP/2 Status:", resp.status_code)
except Exception as e:
    print("HTTP/2 failed:", type(e).__name__, e)

