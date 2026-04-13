"""Assistente de Transcricao — Interface Experimental em Flet.

Usage:
    uv run python main_flet.py
"""
import sys
import flet as ft

# Validar o ambiente e carregar .env antes de rodar o framework
try:
    import app.config  # noqa: F401
except RuntimeError as exc:
    print(f"[ERRO DE CONFIGURACAO] {exc}", file=sys.stderr)
    sys.exit(1)

from app.database import initialize_db
from app.ui_flet.main_app import init_app


def main(page: ft.Page) -> None:
    """Ponto de entrada do Flet."""
    # 1. Iniciar Banco de Dados
    initialize_db()
    
    # 2. Iniciar a UI e atrelar a página
    init_app(page)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
