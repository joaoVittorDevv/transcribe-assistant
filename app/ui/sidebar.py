"""app.ui.sidebar — Prompt selection sidebar.

Displays all saved prompts as a scrollable radio-button list. The
active prompt drives the transcription context (text + glossary).
"""

from typing import Callable

import customtkinter as ctk

import app.database as db
from app.ui.prompt_modal import PromptModal


class Sidebar(ctk.CTkFrame):
    """Left-side panel for selecting the active transcription prompt.

    Args:
        master:            Parent widget.
        on_prompt_changed: Called whenever a different prompt is selected.
    """

    def __init__(
        self,
        master,
        on_prompt_changed: Callable[[], None] | None = None,
        **kwargs,
    ) -> None:
        kwargs.setdefault("width", 220)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)

        self._on_prompt_changed = on_prompt_changed
        self._selected_var = ctk.IntVar(value=-1)  # -1 = none selected
        self._prompts: list = []

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active_prompt(self) -> dict | None:
        """Return the currently selected prompt data or None.

        Returns a dict with keys: id, nome, texto_prompt, palavras_chave (list[str]).
        """
        pid = self._selected_var.get()
        if pid == -1:
            return None

        prompt = db.get_prompt_by_id(pid)
        if prompt is None:
            return None

        keywords = db.get_keywords_by_prompt(pid)
        return {
            "id": prompt["id"],
            "nome": prompt["nome"],
            "texto_prompt": prompt["texto_prompt"],
            "palavras_chave": [row["palavra"] for row in keywords],
        }

    def refresh(self) -> None:
        """Reload prompts from the database and rebuild the radio list."""
        self._prompts = db.get_all_prompts()
        self._render_prompt_list()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Prompt Ativo",
            font=("", 13, "bold"),
        ).grid(row=0, column=0, padx=12, pady=(14, 6), sticky="w")

        self._scroll = ctk.CTkScrollableFrame(self, label_text="")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self._scroll.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            self,
            text="⚙  Gerenciar Prompts",
            command=self._open_prompt_modal,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
        ).grid(row=2, column=0, padx=10, pady=(4, 12), sticky="ew")

    def _render_prompt_list(self) -> None:
        for widget in self._scroll.winfo_children():
            widget.destroy()

        if not self._prompts:
            ctk.CTkLabel(
                self._scroll,
                text="Nenhum prompt\ncadastrado.",
                text_color="gray",
                justify="center",
            ).pack(pady=20)
            return

        # Deselect if the previously selected prompt no longer exists
        ids = {p["id"] for p in self._prompts}
        if self._selected_var.get() not in ids:
            self._selected_var.set(-1)

        for prompt in self._prompts:
            radio = ctk.CTkRadioButton(
                self._scroll,
                text=prompt["nome"],
                variable=self._selected_var,
                value=prompt["id"],
                command=self._on_radio_changed,
            )
            radio.pack(anchor="w", padx=8, pady=4)

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------

    def _on_radio_changed(self) -> None:
        if self._on_prompt_changed:
            self._on_prompt_changed()

    def _open_prompt_modal(self) -> None:
        PromptModal(self, on_changed=self._on_modal_closed)

    def _on_modal_closed(self) -> None:
        self.refresh()
        if self._on_prompt_changed:
            self._on_prompt_changed()
