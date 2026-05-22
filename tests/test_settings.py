"""tests/test_settings.py — Unit and integration tests for secure settings and encryption fallback."""

import os
import tempfile
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Usaremos um arquivo temporário de banco de dados para evitar mexer no banco real de produção
@pytest.fixture
def temp_db():
    temp_dir = tempfile.TemporaryDirectory()
    temp_db_path = Path(temp_dir.name) / "test_transcriber.db"
    
    # Faz backup do DATABASE_PATH original
    import app.config as config
    import app.database as database
    old_path = config.DATABASE_PATH
    
    # Atualiza as variáveis de path nos módulos importados
    config.DATABASE_PATH = temp_db_path
    database.DATABASE_PATH = temp_db_path
    
    # Inicializa o banco de dados temporário
    database.initialize_db()
    
    yield temp_db_path
    
    # Restaura
    config.DATABASE_PATH = old_path
    database.DATABASE_PATH = old_path
    temp_dir.cleanup()


def test_db_settings_crud(temp_db):
    """Testa se as operações básicas de CRUD de configurações funcionam no SQLite."""
    import app.database as db
    
    # get_setting padrão
    assert db.get_setting("CHAVE_INEXISTENTE", "padrão") == "padrão"
    
    # set_setting
    db.set_setting("MINHA_CHAVE", "meu_valor")
    assert db.get_setting("MINHA_CHAVE") == "meu_valor"
    
    # delete_setting
    db.delete_setting("MINHA_CHAVE")
    assert db.get_setting("MINHA_CHAVE") is None


def test_encryption_with_keyring():
    """Testa criptografia e descriptografia usando o fluxo do Keyring."""
    import app.security as sec
    
    # Limpa o cache para forçar nova verificação de chave
    sec._CACHED_KEY = None
    
    mock_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"  # 32 bytes hex
    
    with patch("keyring.get_password") as mock_get, \
         patch("keyring.set_password") as mock_set:
        
        mock_get.return_value = mock_key
        
        # Criptografa um valor
        texto_original = "minha_chave_secreta_super_forte_123"
        texto_criptografado = sec.encrypt_value(texto_original)
        
        assert texto_criptografado != texto_original
        assert ":" in texto_criptografado
        
        # Descriptografa
        texto_descriptografado = sec.decrypt_value(texto_criptografado)
        assert texto_descriptografado == texto_original
        
        # Verifica se o get_password foi chamado
        mock_get.assert_called_with(sec.SERVICE_NAME, sec.ACCOUNT_NAME)
        # set_password não deve ter sido chamado porque get_password retornou uma chave
        mock_set.assert_not_called()


def test_encryption_keyring_creation():
    """Testa a geração de chave nova e gravação no Keyring caso ela não exista."""
    import app.security as sec
    sec._CACHED_KEY = None
    
    stored_keys = {}
    def mock_get(service, account):
        return stored_keys.get((service, account), None)
    
    def mock_set(service, account, value):
        stored_keys[(service, account)] = value
        
    with patch("keyring.get_password", side_effect=mock_get), \
         patch("keyring.set_password", side_effect=mock_set):
        
        # Chama get_or_create_master_key, que deve criar uma chave
        key = sec.get_or_create_master_key()
        assert len(key) == 32
        
        # Verifica se a chave foi setada no keyring em formato hex
        key_hex = stored_keys[(sec.SERVICE_NAME, sec.ACCOUNT_NAME)]
        assert bytes.fromhex(key_hex) == key
        
        # Verifica se a segunda chamada retorna a mesma chave (do cache ou do keyring)
        sec._CACHED_KEY = None  # Limpa cache de memória
        key_second = sec.get_or_create_master_key()
        assert key_second == key


def test_encryption_keyring_fallback():
    """Testa se o fallback do sistema é ativado caso o Keyring jogue exceção ou falhe."""
    import app.security as sec
    sec._CACHED_KEY = None
    
    # Mocking keyring to fail
    with patch("keyring.get_password", side_effect=Exception("Keyring is broken")), \
         patch("app.security._get_system_fallback_key") as mock_fallback:
        
        mock_fallback.return_value = b"f" * 32
        
        key = sec.get_or_create_master_key()
        assert key == b"f" * 32
        mock_fallback.assert_called_once()


def test_encryption_fallback_reproducibility():
    """Testa se a chave de fallback é reproduzível e tem 32 bytes."""
    import app.security as sec
    key1 = sec._get_system_fallback_key()
    key2 = sec._get_system_fallback_key()
    
    assert len(key1) == 32
    assert key1 == key2


def test_config_migration(temp_db):
    """Testa a migração do arquivo .env para o banco de dados na primeira execução."""
    import app.config as config
    import app.database as db
    import app.security as sec
    
    # Mock de variáveis de ambiente do .env
    env_vars = {
        "GOOGLE_API_KEY": "fake_google_key",
        "GROQ_API_KEY": "fake_groq_key",
        "GEMINI_MODEL": "gemini-test-model",
        "NETWORK_PING_HOST": "1.1.1.1",
        "NETWORK_PING_PORT": "80",
        "NETWORK_CHECK_INTERVAL": "5"
    }
    
    with patch.dict(os.environ, env_vars):
        # Chama a migração/leitura
        config.load_all_settings()
        
    # Verifica se as chaves foram criptografadas e salvas no banco
    enc_google = db.get_setting("GOOGLE_API_KEY")
    assert enc_google is not None
    assert enc_google != "fake_google_key"
    assert sec.decrypt_value(enc_google) == "fake_google_key"
    
    enc_groq = db.get_setting("GROQ_API_KEY")
    assert sec.decrypt_value(enc_groq) == "fake_groq_key"
    
    # Verifica valores simples
    assert db.get_setting("GEMINI_MODEL") == "gemini-test-model"
    assert db.get_setting("NETWORK_PING_HOST") == "1.1.1.1"
    assert db.get_setting("NETWORK_PING_PORT") == "80"
    assert db.get_setting("NETWORK_CHECK_INTERVAL") == "5"


def test_config_reload_and_propagation(temp_db):
    """Testa se o reload_config() recarrega os dados e propaga para módulos dependentes."""
    import app.config as config
    import app.database as db
    
    # Setup inicial no banco temporário
    # Definindo APP_LANGUAGE para fazer com que o sistema identifique que o banco já tem dados
    # e evite migrar as variáveis de ambiente reais do sistema
    db.set_setting("APP_LANGUAGE", "pt")
    db.set_setting("GEMINI_MODEL", "gemini-2.0-flash")
    db.set_setting("NETWORK_PING_HOST", "8.8.8.8")
    
    config.load_all_settings()
    assert config.GEMINI_MODEL == "gemini-2.0-flash"
    assert config.NETWORK_PING_HOST == "8.8.8.8"
    
    # Agora mudamos no banco
    db.set_setting("GEMINI_MODEL", "gemini-super-new")
    db.set_setting("NETWORK_PING_HOST", "4.4.4.4")
    
    # Criamos um módulo mock importando de app.config
    import sys
    from types import ModuleType
    
    mock_module = ModuleType("app.mock_service")
    mock_module.GEMINI_MODEL = "gemini-2.0-flash"
    mock_module.NETWORK_PING_HOST = "8.8.8.8"
    sys.modules["app.mock_service"] = mock_module
    
    try:
        # Recarrega a configuração
        config.reload_config()
        
        # Verifica se o config em si mudou
        assert config.GEMINI_MODEL == "gemini-super-new"
        assert config.NETWORK_PING_HOST == "4.4.4.4"
        
        # Verifica se propagou para app.mock_service
        assert mock_module.GEMINI_MODEL == "gemini-super-new"
        assert mock_module.NETWORK_PING_HOST == "4.4.4.4"
    finally:
        sys.modules.pop("app.mock_service", None)
