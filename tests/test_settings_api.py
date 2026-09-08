"""tests/test_settings_api.py — Integration tests for FastAPI settings routes."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.server import app

@pytest.fixture
def temp_db_client():
    temp_dir = tempfile.TemporaryDirectory()
    temp_db_path = Path(temp_dir.name) / "test_transcriber_api.db"
    
    # Backup database paths
    import app.config as config
    import app.database as database
    old_path = config.DATABASE_PATH
    
    # Configure temp database path
    config.DATABASE_PATH = temp_db_path
    
    # Initialize database
    database.initialize_db()
    
    # Seed essential settings
    database.set_setting("APP_LANGUAGE", "pt")
    database.set_setting("GEMINI_MODEL", "gemini-2.0-flash")
    database.set_setting("GROQ_REVIEW_MODEL", "llama-3.1-70b")
    
    client = TestClient(app)
    
    yield client
    
    # Restore config paths
    config.DATABASE_PATH = old_path
    temp_dir.cleanup()


def test_get_settings_route(temp_db_client):
    """Test retrieving masked settings from GET /settings."""
    import app.database as db
    import app.security as sec
    
    # Set encrypted keys in DB
    db.set_setting("GOOGLE_API_KEY", sec.encrypt_value("AIzaSyTestGoogleKey123"))
    db.set_setting("GROQ_API_KEY", sec.encrypt_value("gsk_TestGroqKey456"))
    
    response = temp_db_client.get("/settings")
    assert response.status_code == 200
    
    data = response.json()
    assert data["gemini_key_configured"] is True
    assert data["gemini_key_masked"].startswith("AIzaSy")
    assert "..." in data["gemini_key_masked"]
    
    assert data["groq_key_configured"] is True
    assert data["groq_key_masked"].startswith("gsk_Te")
    assert "..." in data["groq_key_masked"]
    
    assert data["gemini_model"] == "gemini-2.0-flash"
    assert data["groq_review_model"] == "llama-3.1-70b"


def test_put_settings_masked_logic(temp_db_client):
    """Test updating settings ensuring masked keys are ignored while other fields change."""
    import app.database as db
    import app.security as sec
    
    original_google_raw = "AIzaSySuperSecretGoogleKey"
    db.set_setting("GOOGLE_API_KEY", sec.encrypt_value(original_google_raw))
    
    # 1. Update other fields sending masked key
    response = temp_db_client.put("/settings", json={
        "gemini_key": "AIzaSy...eKey",  # Masked
        "gemini_model": "gemini-1.5-pro",
        "app_language": "en"
    })
    assert response.status_code == 200
    assert response.json()["ok"] is True
    
    # The key in DB should remain original decrypted value
    db_google_enc = db.get_setting("GOOGLE_API_KEY")
    assert sec.decrypt_value(db_google_enc) == original_google_raw
    
    # Model and language should be updated
    assert db.get_setting("GEMINI_MODEL") == "gemini-1.5-pro"
    assert db.get_setting("APP_LANGUAGE") == "en"

    # 2. Update with raw new key
    new_google_raw = "AIzaSyBrandNewKey12345"
    response = temp_db_client.put("/settings", json={
        "gemini_key": new_google_raw,
        "gemini_model": "gemini-1.5-pro",
        "app_language": "en"
    })
    assert response.status_code == 200
    db_google_enc_new = db.get_setting("GOOGLE_API_KEY")
    assert sec.decrypt_value(db_google_enc_new) == new_google_raw


@patch("app.models_fetcher.fetch_gemini_models")
@patch("app.models_fetcher.fetch_groq_models")
def test_fetch_models_route(mock_groq_fetch, mock_gemini_fetch, temp_db_client):
    """Test dynamic fetching of models endpoint."""
    mock_gemini_fetch.return_value = ["gemini-a", "gemini-b"]
    mock_groq_fetch.return_value = ["groq-x", "groq-y"]
    
    import app.database as db
    import app.security as sec
    db.set_setting("GOOGLE_API_KEY", sec.encrypt_value("AIzaSyMyDecryptedKey"))
    
    # 1. Fetching models using masked key (should fallback to decrypted DB key)
    response = temp_db_client.post("/settings/models", json={
        "gemini_key": "AIzaSy...edKey",
        "groq_key": ""
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["gemini_models"] == ["gemini-a", "gemini-b"]
    mock_gemini_fetch.assert_called_with("AIzaSyMyDecryptedKey")
    
    # 2. Fetching models sending new temporary key
    response = temp_db_client.post("/settings/models", json={
        "gemini_key": "AIzaSyNewTmpKey",
        "groq_key": ""
    })
    assert response.status_code == 200
    mock_gemini_fetch.assert_called_with("AIzaSyNewTmpKey")
