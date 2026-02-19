"""Assistente de Transcricao — entry point.

Usage:
    uv run main.py
    python main.py
"""

import sys

# Validate environment before building any UI
try:
    import app.config  # noqa: F401 — triggers .env load + validation
except RuntimeError as exc:
    print(f"[ERRO DE CONFIGURACAO] {exc}", file=sys.stderr)
    sys.exit(1)

from app.database import initialize_db
from app.ui.main_window import MainWindow


def main() -> None:
    initialize_db()
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
