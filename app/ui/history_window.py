"""app.ui.history_window — Session history browser.

Lists past transcription sessions with options to copy the text or
restore a session (loading it back into the main window for further
appending).
"""

import i18n
from typing import Callable

import customtkinter as ctk

import app.database as db


class HistoryWindow(ctk.CTkToplevel):
    """Toplevel window that lists all past transcription sessions.

    Args:
        master:       Parent widget.
        on_restore:   Callback invoked when user clicks "Restaurar".
                      Receives (session_id: int, text: str).
    """

    def __init__(
        self,
        master,
        on_restore: Callable[[int, str], None] | None = None,
    ) -> None:
        super().__init__(master)
        self._on_restore = on_restore

        self.title(i18n.t("ui.history.title"))
        self.geometry("680x480")
        self.resizable(True, True)

        # DEBUG - REMOVE LATER
        print("[DEBUG] HistoryWindow.__init__ chamado")

        # Defer UI build to ensure the CTkToplevel is rendered first (Linux fix)
        self.after(10, self._delayed_init)

    def refresh_labels(self) -> None:
        self.title(i18n.t("ui.history.title"))
        self._title_label.configure(text=i18n.t("ui.history.title"))
        if (
            hasattr(self, "_no_sessions_label")
            and self._no_sessions_label.winfo_exists()
        ):
            self._no_sessions_label.configure(text=i18n.t("ui.history.no_sessions"))
        # As session cards create dynamically, we'd ideally recreate them or keep references.
        # But for full i18n correctness we can just reload sessions entirely.
        self._load_sessions()

    def _delayed_init(self) -> None:
        """Build UI after window is rendered. Required on Linux/X11."""
        # DEBUG - REMOVE LATER
        print("[DEBUG] HistoryWindow._delayed_init chamado — construindo UI")
        self._build_ui()
        self._load_sessions()
        self.refresh_labels()
        self.after(150, self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
            # DEBUG - REMOVE LATER
            print("[DEBUG] HistoryWindow.grab_set() bem-sucedido")
        except Exception as exc:  # noqa: BLE001
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] HistoryWindow.grab_set() falhou (ignorado): {exc}")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._title_label = ctk.CTkLabel(
            self,
            text=i18n.t("ui.history.title"),
            font=("", 16, "bold"),
        )
        self._title_label.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        self._scroll = ctk.CTkScrollableFrame(self, label_text="")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._scroll.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Session list
    # ------------------------------------------------------------------

    def _load_sessions(self) -> None:
        for widget in self._scroll.winfo_children():
            widget.destroy()

        sessions = db.get_all_sessions()

        if not sessions:
            self._no_sessions_label = ctk.CTkLabel(
                self._scroll,
                text=i18n.t("ui.history.no_sessions"),
                text_color="gray",
            )
            self._no_sessions_label.pack(pady=20)
            return

        for session in sessions:
            self._add_session_card(session)

    def _add_session_card(self, session) -> None:
        """Render a single session card in the scrollable list."""
        card = ctk.CTkFrame(self._scroll, corner_radius=8)
        card.pack(fill="x", padx=4, pady=6)
        card.grid_columnconfigure(0, weight=1)

        # Header row: date + interaction count
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        header.grid_columnconfigure(0, weight=1)

        date_label = ctk.CTkLabel(
            header,
            text=f"📅  {session['atualizado_em']}",
            font=("", 11),
            text_color="gray",
            anchor="w",
        )
        date_label.grid(row=0, column=0, sticky="w")

        interactions_label = ctk.CTkLabel(
            header,
            text=i18n.t(
                "ui.history.interactions", count=session["quantidade_interacoes"]
            ),
            font=("", 11),
            text_color="gray",
            anchor="e",
        )
        interactions_label.grid(row=0, column=1, sticky="e")

        # Preview of the text (first 200 chars)
        preview = session["conteudo_texto"][:220].replace("\n", " ")
        if len(session["conteudo_texto"]) > 220:
            preview += "…"

        ctk.CTkLabel(
            card,
            text=preview,
            anchor="w",
            justify="left",
            wraplength=580,
        ).grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")

        # Action buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="e")

        ctk.CTkButton(
            btn_row,
            text=i18n.t("ui.buttons.copy"),
            width=90,
            command=lambda s=session: self._copy_session(s),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row,
            text=i18n.t("ui.buttons.restore"),
            width=90,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=lambda s=session: self._restore_session(s),
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _copy_session(self, session) -> None:
        self.clipboard_clear()
        self.clipboard_append(session["conteudo_texto"])

    def _restore_session(self, session) -> None:
        if self._on_restore:
            self._on_restore(session["id"], session["conteudo_texto"])
        self.destroy()
