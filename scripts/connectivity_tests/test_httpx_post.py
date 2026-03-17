import httpx
from app.config import GOOGLE_API_KEY
import ssl

print("Testing httpx POST...")
try:
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    headers = {
        "x-goog-api-key": GOOGLE_API_KEY,
        "content-type": "application/json",
        "user-agent": "google-genai-sdk/0.1.0"
    }
    payload = {
        "contents": [{"parts": [{"text": "Hello, are you there?"}]}]
    }
    with httpx.Client(http2=False) as c:
        resp = c.post(url, headers=headers, json=payload, timeout=60.0)
        print("Status:", resp.status_code)
        print("Body:", resp.text[:100])
except Exception as e:
    print("POST failed:", type(e).__name__, e)
