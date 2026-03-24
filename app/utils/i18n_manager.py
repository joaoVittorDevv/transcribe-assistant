"""Gerenciador de Internacionalização (i18n) via Dicionário Python.

Centraliza todas as strings da interface para suportar troca dinâmica de idiomas
sem recarga total da UI.
"""

from __future__ import annotations

from typing import Dict


class I18nManager:
    """Gerenciador Singleton de traduções PT/EN."""

    _STRINGS: Dict[str, Dict[str, str]] = {
        "pt": {
            "app_title": "Assistente de Transcrição",
            "history": "Histórico",
            "online": "Online ⚡",
            "record": "Gravar",
            "recording": "Gravando...",
            "transcribe": "Transcrever",
            "processing": "Processando...",
            "cancel": "Cancelar",
            "copy": "Copiar",
            "clear": "Limpar",
            "upload": "Enviar Arquivo",
            "ready": "Pronto.",
            "copied": "Texto copiado!",
            "context_reset": "Contexto resetado.",
            "transcribing": "Transcrevendo áudio...",
            "mic_mode": "Microfone",
            "system_mode": "Sistema",
            "select_file": "Selecione um arquivo de áudio",
            "language": "Idioma",
        },
        "en": {
            "app_title": "Transcription Assistant",
            "history": "History",
            "online": "Online ⚡",
            "record": "Record",
            "recording": "Recording...",
            "transcribe": "Transcribe",
            "processing": "Processing...",
            "cancel": "Cancel",
            "copy": "Copy",
            "clear": "Clear",
            "upload": "Upload File",
            "ready": "Ready.",
            "copied": "Text copied!",
            "context_reset": "Context reset.",
            "transcribing": "Transcribing audio...",
            "mic_mode": "Microphone",
            "system_mode": "System",
            "select_file": "Select an audio file",
            "language": "Language",
        },
    }

    def __init__(self, default_lang: str = "pt") -> None:
        self.current_lang: str = default_lang

    def get(self, key: str) -> str:
        """Retorna a string correspondente à chave no idioma atual."""
        return self._STRINGS.get(self.current_lang, self._STRINGS["pt"]).get(key, key)

    def set_language(self, lang: str) -> None:
        """Altera o idioma globalmente."""
        if lang in self._STRINGS:
            self.current_lang = lang


# Instância Singleton padrão
i18n = I18nManager()
