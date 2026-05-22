"""app.models_fetcher — Fetch available models from Google Gemini and Groq APIs.

Provides helpers to dynamically query available models from the external APIs
using their SDKs or direct HTTP requests as a robust fallback.
"""

import json
import urllib.request
from typing import List

# Default model fallbacks in case APIs are unreachable
DEFAULT_GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

DEFAULT_GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
    "whisper-large-v3",
]


def fetch_gemini_models(api_key: str) -> List[str]:
    """Fetch available models from the Google Gemini API.

    Attempts to use the official `google-genai` SDK first, falling back to
    a direct REST HTTP call if the SDK fails or is not installed.
    """
    if not api_key:
        return DEFAULT_GEMINI_MODELS

    # Try SDK first
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        # client.models.list() returns an iterable of Model objects
        models_list = list(client.models.list())
        
        # Filter for models containing 'gemini' (excluding embeddings, etc.)
        gemini_models = []
        for m in models_list:
            name = m.name or ""
            # Strip "models/" prefix if present
            if name.startswith("models/"):
                name = name[len("models/"):]
            
            if "gemini" in name.lower() and not any(
                x in name.lower() for x in ["embed", "vision-free", "classification"]
            ):
                gemini_models.append(name)
        
        if gemini_models:
            return sorted(list(set(gemini_models)))
    except Exception as e:
        print(f"[MODELS FETCHER] Gemini SDK listing failed: {e}. Trying REST fallback...")

    # REST Fallback
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            gemini_models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                if name.startswith("models/"):
                    name = name[7:]
                
                # Filter useful transcription/text models
                if "gemini" in name.lower() and not any(
                    x in name.lower() for x in ["embed", "vision-free", "classification"]
                ):
                    gemini_models.append(name)
            
            if gemini_models:
                return sorted(list(set(gemini_models)))
    except Exception as e:
        print(f"[MODELS FETCHER] Gemini REST API fallback failed: {e}")

    return DEFAULT_GEMINI_MODELS


def fetch_groq_models(api_key: str) -> List[str]:
    """Fetch available models from the Groq API.

    Attempts to use the official `groq` SDK first, falling back to
    a direct REST HTTP call if the SDK fails or is not installed.
    """
    if not api_key:
        return DEFAULT_GROQ_MODELS

    # Try SDK first
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        models_list = client.models.list()
        
        # models_list is an object containing 'data' field (list of models)
        groq_models = []
        for m in models_list.data:
            model_id = getattr(m, "id", "")
            if model_id and not any(
                x in model_id.lower() for x in ["whisper-large-v3-turbo", "guard"]
            ):
                groq_models.append(model_id)
        
        if groq_models:
            return sorted(list(set(groq_models)))
    except Exception as e:
        print(f"[MODELS FETCHER] Groq SDK listing failed: {e}. Trying REST fallback...")

    # REST Fallback
    try:
        url = "https://api.groq.com/openai/v1/models"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            groq_models = []
            for m in data.get("data", []):
                model_id = m.get("id", "")
                if model_id and not any(
                    x in model_id.lower() for x in ["whisper-large-v3-turbo", "guard"]
                ):
                    groq_models.append(model_id)
            
            if groq_models:
                return sorted(list(set(groq_models)))
    except Exception as e:
        print(f"[MODELS FETCHER] Groq REST API fallback failed: {e}")

    return DEFAULT_GROQ_MODELS
