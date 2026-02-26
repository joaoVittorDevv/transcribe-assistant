"""app.database — SQLite persistence layer.

Handles schema initialization and all CRUD operations for the three tables:
  - prompts       : user-defined transcription instructions
  - palavras_chave: glossary keywords linked to a prompt
  - sessions      : transcription history (incremental sessions)

All functions open/close their own connection for thread safety.
The database file path is taken from app.config.DATABASE_PATH.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator

from app.config import DATABASE_PATH

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


@contextmanager
def _connect() -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection with row_factory and foreign key support."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def initialize_db() -> None:
    """Create all tables if they do not exist yet."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS prompts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                nome         TEXT    NOT NULL,
                texto_prompt TEXT    NOT NULL DEFAULT '',
                is_default   BOOLEAN DEFAULT 0,
                criado_em    DATETIME DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS palavras_chave (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id INTEGER NOT NULL,
                palavra   TEXT    NOT NULL,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo                TEXT    NOT NULL DEFAULT 'Nova Sessão',
                conteudo_texto        TEXT    NOT NULL DEFAULT '',
                quantidade_interacoes INTEGER NOT NULL DEFAULT 0,
                criado_em             DATETIME DEFAULT (datetime('now')),
                atualizado_em         DATETIME DEFAULT (datetime('now'))
            );
        """
        )

        # Migration: Add titulo column if it doesn't exist
        try:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN titulo TEXT NOT NULL DEFAULT 'Nova Sessão'"
            )
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Migration: Add is_default column to prompts if it doesn't exist
        try:
            conn.execute("ALTER TABLE prompts ADD COLUMN is_default BOOLEAN DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists


# ---------------------------------------------------------------------------
# Prompts CRUD
# ---------------------------------------------------------------------------


def create_prompt(nome: str, texto_prompt: str, is_default: bool = False) -> int:
    """Insert a new prompt and return its id."""
    with _connect() as conn:
        if is_default:
            conn.execute("UPDATE prompts SET is_default = 0")

        cursor = conn.execute(
            "INSERT INTO prompts (nome, texto_prompt, is_default) VALUES (?, ?, ?)",
            (nome, texto_prompt, is_default),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_all_prompts() -> list[sqlite3.Row]:
    """Return all prompts ordered by creation date (newest first)."""
    with _connect() as conn:
        return conn.execute("SELECT * FROM prompts ORDER BY criado_em DESC").fetchall()


def get_prompt_by_id(prompt_id: int) -> sqlite3.Row | None:
    """Return a single prompt by id, or None if not found."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
        ).fetchone()


def update_prompt(
    prompt_id: int, nome: str, texto_prompt: str, is_default: bool = False
) -> None:
    """Update nome, texto_prompt, and is_default of an existing prompt."""
    with _connect() as conn:
        if is_default:
            conn.execute(
                "UPDATE prompts SET is_default = 0 WHERE id != ?", (prompt_id,)
            )

        conn.execute(
            "UPDATE prompts SET nome = ?, texto_prompt = ?, is_default = ? WHERE id = ?",
            (nome, texto_prompt, is_default, prompt_id),
        )


def get_default_prompt() -> sqlite3.Row | None:
    """Return the default prompt, or None if not set."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM prompts WHERE is_default = 1 LIMIT 1"
        ).fetchone()


def delete_prompt(prompt_id: int) -> None:
    """Delete a prompt and cascade-delete its keywords."""
    with _connect() as conn:
        conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))


# ---------------------------------------------------------------------------
# Keywords (glossary) CRUD
# ---------------------------------------------------------------------------


def add_keyword(prompt_id: int, palavra: str) -> int:
    """Insert a keyword linked to a prompt and return its id."""
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO palavras_chave (prompt_id, palavra) VALUES (?, ?)",
            (prompt_id, palavra.strip()),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_keywords_by_prompt(prompt_id: int) -> list[sqlite3.Row]:
    """Return all keywords for a given prompt."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM palavras_chave WHERE prompt_id = ? ORDER BY id",
            (prompt_id,),
        ).fetchall()


def replace_keywords(prompt_id: int, palavras: list[str]) -> None:
    """Replace all keywords for a prompt atomically.

    Deletes existing keywords and inserts the new list in one transaction.
    """
    with _connect() as conn:
        conn.execute("DELETE FROM palavras_chave WHERE prompt_id = ?", (prompt_id,))
        conn.executemany(
            "INSERT INTO palavras_chave (prompt_id, palavra) VALUES (?, ?)",
            [(prompt_id, p.strip()) for p in palavras if p.strip()],
        )


# ---------------------------------------------------------------------------
# Sessions CRUD
# ---------------------------------------------------------------------------


def create_session(conteudo_texto: str, titulo: str = "Nova Sessão") -> int:
    """Create a new transcription session and return its id."""
    with _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO sessions (conteudo_texto, titulo, quantidade_interacoes)
               VALUES (?, ?, 1)""",
            (conteudo_texto, titulo),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def update_session(session_id: int, novo_trecho: str) -> None:
    """Append text to an existing session and increment interaction count."""
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """UPDATE sessions
               SET conteudo_texto        = conteudo_texto || ' ' || ?,
                   quantidade_interacoes = quantidade_interacoes + 1,
                   atualizado_em         = ?
               WHERE id = ?""",
            (novo_trecho, now, session_id),
        )


def overwrite_session_content(
    session_id: int, full_text: str, update_interactions: bool = False
) -> None:
    """Overwrite the session content entirely.

    Used when the user manually edits the text or when inserting at a specific cursor position.
    """
    now = datetime.now().isoformat(sep=" ", timespec="seconds")

    with _connect() as conn:
        if update_interactions:
            conn.execute(
                """UPDATE sessions
                   SET conteudo_texto        = ?,
                       quantidade_interacoes = quantidade_interacoes + 1,
                       atualizado_em         = ?
                   WHERE id = ?""",
                (full_text, now, session_id),
            )
        else:
            conn.execute(
                """UPDATE sessions
                   SET conteudo_texto = ?,
                       atualizado_em  = ?
                   WHERE id = ?""",
                (full_text, now, session_id),
            )


def get_all_sessions() -> list[sqlite3.Row]:
    """Return all sessions ordered by most recently updated."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions ORDER BY atualizado_em DESC"
        ).fetchall()


def get_session_by_id(session_id: int) -> sqlite3.Row | None:
    """Return a single session by id, or None if not found."""
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()


def update_session_title(session_id: int, titulo: str) -> None:
    """Update the title of an existing session."""
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET titulo = ? WHERE id = ?",
            (titulo, session_id),
        )


def delete_session(session_id: int) -> None:
    """Delete a session from the database."""
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
