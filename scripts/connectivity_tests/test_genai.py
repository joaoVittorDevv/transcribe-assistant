import os
from app.config import GOOGLE_API_KEY, GEMINI_TIMEOUT, GEMINI_MODEL
from google import genai
from google.genai import types

print(f"Key preview: {GOOGLE_API_KEY[:5]}... Timeout: {GEMINI_TIMEOUT}")

try:
    client = genai.Client(
        api_key=GOOGLE_API_KEY, 
        http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT * 1000.0)
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL, 
        contents='Hello, are you there?'
    )
    print("Success:", response.text[:50])
except Exception as e:
    import traceback
    traceback.print_exc()
