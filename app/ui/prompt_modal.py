"""app.ui.prompt_modal — Modal for editing the default prompt and glossary."""

import i18n
from typing import Callable

import customtkinter as ctk

import app.database as db


class PromptModal(ctk.CTkToplevel):
    """Modal window for editing the default system prompt and its glossary."""

    def __init__(
        self,
        master,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self._on_changed = on_changed
        self._keyword_vars: list[str] = []

        self.title(i18n.t("ui.prompts.title"))
        self.geometry("620x520")
        self.resizable(False, False)

        self.after(10, self._delayed_init)

    def refresh_labels(self) -> None:
        self.title(i18n.t("ui.prompts.title"))
        self._name_label.configure(text=i18n.t("ui.prompts.name_label"))
        self._name_entry.configure(
            placeholder_text=i18n.t("ui.prompts.name_placeholder")
        )
        self._text_label.configure(text=i18n.t("ui.prompts.text_label"))
        self._glossary_label.configure(text=i18n.t("ui.prompts.glossary_label"))
        self._keyword_entry.configure(
            placeholder_text=i18n.t("ui.prompts.add_keyword_placeholder")
        )
        self._add_kw_btn.configure(text=i18n.t("ui.buttons.add"))
        self._save_btn.configure(text=i18n.t("ui.buttons.save"))

    # ------------------------------------------------------------------
    # Delayed init (CTkToplevel Linux race condition fix)
    # ------------------------------------------------------------------

    def _delayed_init(self) -> None:
        self._build_ui()
        self._load_default_prompt()
        self.after(150, self._safe_grab)

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- Single-column form panel ----
        form = ctk.CTkFrame(self, corner_radius=0)
        form.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        form.grid_columnconfigure(0, weight=1)

        # Name
        self._name_label = ctk.CTkLabel(form, text=i18n.t("ui.prompts.name_label"))
        self._name_label.grid(row=0, column=0, sticky="w", pady=(0, 2))

        self._name_entry = ctk.CTkEntry(
            form, placeholder_text=i18n.t("ui.prompts.name_placeholder")
        )
        self._name_entry.grid(row=1, column=0, sticky="ew", pady=(0, 14))

        # Prompt text
        self._text_label = ctk.CTkLabel(form, text=i18n.t("ui.prompts.text_label"))
        self._text_label.grid(row=2, column=0, sticky="w", pady=(0, 2))

        self._prompt_text = ctk.CTkTextbox(form, height=140)
        self._prompt_text.grid(row=3, column=0, sticky="nsew", pady=(0, 14))
        form.grid_rowconfigure(3, weight=1)

        # Glossary
        self._glossary_label = ctk.CTkLabel(
            form, text=i18n.t("ui.prompts.glossary_label")
        )
        self._glossary_label.grid(row=4, column=0, sticky="w", pady=(0, 2))

        kw_frame = ctk.CTkFrame(form, fg_color="transparent")
        kw_frame.grid(row=5, column=0, sticky="ew", pady=(0, 6))
        kw_frame.grid_columnconfigure(0, weight=1)

        self._keyword_entry = ctk.CTkEntry(
            kw_frame, placeholder_text=i18n.t("ui.prompts.add_keyword_placeholder")
        )
        self._keyword_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._keyword_entry.bind("<Return>", lambda _: self._add_keyword())

        self._add_kw_btn = ctk.CTkButton(
            kw_frame, text=i18n.t("ui.buttons.add"), width=36, command=self._add_keyword
        )
        self._add_kw_btn.grid(row=0, column=1)

        self._keywords_frame = ctk.CTkScrollableFrame(form, height=80)
        self._keywords_frame.grid(row=6, column=0, sticky="ew", pady=(0, 16))

        # Save button
        self._save_btn = ctk.CTkButton(
            form,
            text=i18n.t("ui.buttons.save"),
            command=self._on_save,
        )
        self._save_btn.grid(row=7, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Load default prompt
    # ------------------------------------------------------------------

    def _load_default_prompt(self) -> None:
        default = db.get_default_prompt()
        if default:
            self._name_entry.insert(0, default["nome"])
            self._prompt_text.insert("1.0", default["texto_prompt"])
            rows = db.get_keywords_by_prompt(default["id"])
            self._keyword_vars = [row["palavra"] for row in rows]
        else:
            self._name_entry.insert(0, "Prompt Padrão")
            self._prompt_text.insert("1.0", "")
            self._keyword_vars = []
        self._render_keywords()

    # ------------------------------------------------------------------
    # Keyword management
    # ------------------------------------------------------------------

    def _add_keyword(self) -> None:
        word = self._keyword_entry.get().strip()
        if word and word not in self._keyword_vars:
            self._keyword_vars.append(word)
            self._keyword_entry.delete(0, "end")
            self._render_keywords()

    def _remove_keyword(self, word: str) -> None:
        self._keyword_vars = [w for w in self._keyword_vars if w != word]
        self._render_keywords()

    def _render_keywords(self) -> None:
        for widget in self._keywords_frame.winfo_children():
            widget.destroy()

        row = col = 0
        max_cols = 4
        for word in self._keyword_vars:
            tag = ctk.CTkFrame(self._keywords_frame, fg_color=("gray80", "gray30"))
            tag.grid(row=row, column=col, padx=3, pady=3, sticky="w")
            ctk.CTkLabel(tag, text=word, padx=6).pack(side="left")
            ctk.CTkButton(
                tag, text="×", width=22, fg_color="transparent",
                command=lambda w=word: self._remove_keyword(w),
            ).pack(side="left")
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _on_save(self) -> None:
        nome = self._name_entry.get().strip()
        texto = self._prompt_text.get("1.0", "end").strip()

        if not nome:
            self._show_error(i18n.t("ui.prompts.error_empty_name"))
            return

        default = db.get_default_prompt()
        if default:
            db.update_prompt(default["id"], nome, texto, is_default=True)
            pid = default["id"]
        else:
            pid = db.create_prompt(nome, texto, is_default=True)

        db.replace_keywords(pid, self._keyword_vars)

        if self._on_changed:
            self._on_changed()

        self.destroy()

    def _show_error(self, message: str) -> None:
        ctk.CTkLabel(self, text=message, text_color="#ef4444").place(
            relx=0.5, rely=0.97, anchor="s"
        )
