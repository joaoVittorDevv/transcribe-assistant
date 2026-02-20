"""app.ui.prompt_modal — CRUD modal for prompts and their glossaries.

Opens as a CTkToplevel window. Supports creating, editing and deleting
prompts, including management of the associated keyword/glossary list.
"""

import i18n
from typing import Callable

import customtkinter as ctk

import app.database as db


class PromptModal(ctk.CTkToplevel):
    """Modal window for full CRUD management of transcription prompts.

    Args:
        master:           Parent widget.
        on_changed:       Callback invoked after any create/update/delete
                          so the sidebar can refresh its list.
    """

    def __init__(
        self,
        master,
        on_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self._on_changed = on_changed
        self._selected_prompt_id: int | None = None
        self._keyword_vars: list[str] = []

        self.title(i18n.t("ui.prompts.title"))
        self.geometry("720x540")
        self.resizable(False, False)

        # DEBUG - REMOVE LATER
        print("[DEBUG] PromptModal.__init__ chamado")

        # Defer UI build to ensure the CTkToplevel is rendered first (Linux fix)
        self.after(10, self._delayed_init)

    def refresh_labels(self) -> None:
        self.title(i18n.t("ui.prompts.title"))
        self._list_title_label.configure(text=i18n.t("ui.prompts.list_title"))
        self._new_btn.configure(text=i18n.t("ui.prompts.new"))

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
        self._delete_btn.configure(text=i18n.t("ui.buttons.delete"))

    # ------------------------------------------------------------------
    # Delayed init (CTkToplevel Linux race condition fix)
    # ------------------------------------------------------------------

    def _delayed_init(self) -> None:
        """Build UI after window is rendered. Required on Linux/X11."""
        # DEBUG - REMOVE LATER
        print("[DEBUG] PromptModal._delayed_init chamado — construindo UI")
        self._build_ui()
        self._load_prompt_list()
        # grab_set after a bit more time to ensure window is "viewable"
        self.after(150, self._safe_grab)

    def _safe_grab(self) -> None:
        """Attempt grab_set safely, ignoring if window is not yet viewable."""
        try:
            self.grab_set()
            # DEBUG - REMOVE LATER
            print("[DEBUG] PromptModal.grab_set() bem-sucedido")
        except Exception as exc:  # noqa: BLE001
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] PromptModal.grab_set() falhou (ignorado): {exc}")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1, minsize=220)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)

        # ---- Left panel: prompt list ----
        left = ctk.CTkFrame(self, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        left.grid_rowconfigure(1, weight=1)

        self._list_title_label = ctk.CTkLabel(
            left, text=i18n.t("ui.prompts.list_title"), font=("", 14, "bold")
        )
        self._list_title_label.grid(row=0, column=0, padx=10, pady=(10, 4), sticky="w")

        self._prompt_listbox = ctk.CTkScrollableFrame(left, label_text="")
        self._prompt_listbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        self._prompt_listbox.grid_columnconfigure(0, weight=1)

        self._new_btn = ctk.CTkButton(
            left, text=i18n.t("ui.prompts.new"), command=self._on_new
        )
        self._new_btn.grid(row=2, column=0, padx=10, pady=(4, 10), sticky="ew")

        # ---- Right panel: form ----
        right = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        self._name_label = ctk.CTkLabel(right, text=i18n.t("ui.prompts.name_label"))
        self._name_label.grid(row=0, column=0, sticky="w", pady=(0, 2))

        self._name_entry = ctk.CTkEntry(
            right, placeholder_text=i18n.t("ui.prompts.name_placeholder")
        )
        self._name_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self._text_label = ctk.CTkLabel(right, text=i18n.t("ui.prompts.text_label"))
        self._text_label.grid(row=2, column=0, sticky="w", pady=(0, 2))

        self._prompt_text = ctk.CTkTextbox(right, height=120)
        self._prompt_text.grid(row=3, column=0, sticky="nsew", pady=(0, 10))

        self._glossary_label = ctk.CTkLabel(
            right, text=i18n.t("ui.prompts.glossary_label")
        )
        self._glossary_label.grid(row=4, column=0, sticky="w", pady=(0, 2))

        kw_frame = ctk.CTkFrame(right, fg_color="transparent")
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

        self._keywords_frame = ctk.CTkScrollableFrame(right, height=80)
        self._keywords_frame.grid(row=6, column=0, sticky="ew", pady=(0, 12))

        # Action buttons
        btn_frame = ctk.CTkFrame(right, fg_color="transparent")
        btn_frame.grid(row=7, column=0, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        self._save_btn = ctk.CTkButton(
            btn_frame, text=i18n.t("ui.buttons.save"), command=self._on_save
        )
        self._save_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._delete_btn = ctk.CTkButton(
            btn_frame,
            text=i18n.t("ui.buttons.delete"),
            fg_color="#ef4444",
            hover_color="#b91c1c",
            command=self._on_delete,
            state="disabled",
        )
        self._delete_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

    # ------------------------------------------------------------------
    # Prompt list
    # ------------------------------------------------------------------

    def _load_prompt_list(self) -> None:
        for widget in self._prompt_listbox.winfo_children():
            widget.destroy()

        prompts = db.get_all_prompts()
        for prompt in prompts:
            btn = ctk.CTkButton(
                self._prompt_listbox,
                text=prompt["nome"],
                anchor="w",
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                command=lambda p=prompt: self._load_prompt_form(p),
            )
            btn.pack(fill="x", pady=2)

    def _load_prompt_form(self, prompt: dict) -> None:
        self._selected_prompt_id = prompt["id"]
        self._delete_btn.configure(state="normal")

        self._name_entry.delete(0, "end")
        self._name_entry.insert(0, prompt["nome"])

        self._prompt_text.delete("1.0", "end")
        self._prompt_text.insert("1.0", prompt["texto_prompt"])

        # Load keywords
        rows = db.get_keywords_by_prompt(prompt["id"])
        self._keyword_vars = [row["palavra"] for row in rows]
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

        for word in self._keyword_vars:
            tag = ctk.CTkFrame(self._keywords_frame, fg_color=("gray80", "gray30"))
            tag.pack(side="left", padx=3, pady=3)
            ctk.CTkLabel(tag, text=word, padx=6).pack(side="left")
            ctk.CTkButton(
                tag,
                text="×",
                width=22,
                fg_color="transparent",
                command=lambda w=word: self._remove_keyword(w),
            ).pack(side="left")

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _on_new(self) -> None:
        self._selected_prompt_id = None
        self._delete_btn.configure(state="disabled")
        self._name_entry.delete(0, "end")
        self._prompt_text.delete("1.0", "end")
        self._keyword_vars = []
        self._render_keywords()

    def _on_save(self) -> None:
        nome = self._name_entry.get().strip()
        texto = self._prompt_text.get("1.0", "end").strip()

        if not nome:
            self._show_error(i18n.t("ui.prompts.error_empty_name"))
            return

        if self._selected_prompt_id is None:
            pid = db.create_prompt(nome, texto)
        else:
            pid = self._selected_prompt_id
            db.update_prompt(pid, nome, texto)

        db.replace_keywords(pid, self._keyword_vars)
        self._selected_prompt_id = pid
        self._delete_btn.configure(state="normal")

        self._load_prompt_list()
        if self._on_changed:
            self._on_changed()

    def _on_delete(self) -> None:
        if self._selected_prompt_id is None:
            return
        db.delete_prompt(self._selected_prompt_id)
        self._on_new()
        self._load_prompt_list()
        if self._on_changed:
            self._on_changed()

    def _show_error(self, message: str) -> None:
        ctk.CTkLabel(
            self,
            text=message,
            text_color="#ef4444",
        ).place(relx=0.5, rely=0.95, anchor="s")
