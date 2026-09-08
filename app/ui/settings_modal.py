"""app.ui.settings_modal — Settings modal window.

Allows users to manage API keys (encrypted), model configurations,
network parameters, folders, and language options directly within the UI.
"""

import threading
import i18n
from typing import Callable, List
import customtkinter as ctk
from tkinter import filedialog, messagebox

import app.config as config
import app.database as db
import app.security as sec
from app.models_fetcher import fetch_gemini_models, fetch_groq_models


class SettingsModal(ctk.CTkToplevel):
    """Modal window to configure all application settings dynamically."""

    def __init__(
        self,
        master,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self._on_saved = on_saved

        self.title(i18n.t("ui.settings.title"))
        self.geometry("640x700")
        self.resizable(False, False)
        self.transient(master)

        # State vars
        self._gemini_key_visible = False
        self._groq_key_visible = False

        # Defer UI build to prevent Linux rendering race conditions
        self.after(10, self._delayed_init)

    def _delayed_init(self) -> None:
        """Delayed initialization to ensure window renders first (Linux fix)."""
        self._build_ui()
        self._load_settings_into_ui()
        self.after(150, self._safe_grab)

    def _safe_grab(self) -> None:
        """Safely grab focus for modal behavior."""
        try:
            self.grab_set()
        except Exception as e:
            print(f"[SETTINGS DEBUG] grab_set failed (ignored): {e}")

    def _build_ui(self) -> None:
        """Create and place widgets using CustomTkinter."""
        # Main layout: Scrollable frame covering the whole window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._scroll_frame = ctk.CTkScrollableFrame(self, label_text=None)
        self._scroll_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 70))
        self._scroll_frame.grid_columnconfigure(0, weight=1)

        # -------------------------------------------------------------------
        # Seção Google Gemini
        # -------------------------------------------------------------------
        gemini_frame = ctk.CTkFrame(self._scroll_frame)
        gemini_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        gemini_frame.grid_columnconfigure(0, weight=1)

        gemini_title = ctk.CTkLabel(
            gemini_frame,
            text=i18n.t("ui.settings.gemini_section"),
            font=ctk.CTkFont(weight="bold", size=14)
        )
        gemini_title.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=10)

        # Gemini Key
        gemini_key_label = ctk.CTkLabel(gemini_frame, text=i18n.t("ui.settings.api_key_label"))
        gemini_key_label.grid(row=1, column=0, sticky="w", padx=10, pady=(2, 0))

        self._gemini_key_entry = ctk.CTkEntry(gemini_frame, show="*")
        self._gemini_key_entry.grid(row=2, column=0, sticky="ew", padx=(10, 5), pady=2)

        self._gemini_toggle_btn = ctk.CTkButton(
            gemini_frame,
            text=i18n.t("ui.settings.show_key"),
            width=50,
            command=self._toggle_gemini_key_visibility
        )
        self._gemini_toggle_btn.grid(row=2, column=1, padx=(0, 10), pady=2)

        # Gemini Model
        gemini_model_label = ctk.CTkLabel(gemini_frame, text=i18n.t("ui.settings.model_label"))
        gemini_model_label.grid(row=3, column=0, sticky="w", padx=10, pady=(5, 0))

        self._gemini_model_combo = ctk.CTkComboBox(gemini_frame, values=[config.GEMINI_MODEL])
        self._gemini_model_combo.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=2)

        # -------------------------------------------------------------------
        # Seção Groq
        # -------------------------------------------------------------------
        groq_frame = ctk.CTkFrame(self._scroll_frame)
        groq_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=10)
        groq_frame.grid_columnconfigure(0, weight=1)

        groq_title = ctk.CTkLabel(
            groq_frame,
            text=i18n.t("ui.settings.groq_section"),
            font=ctk.CTkFont(weight="bold", size=14)
        )
        groq_title.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=10)

        # Groq Key
        groq_key_label = ctk.CTkLabel(groq_frame, text=i18n.t("ui.settings.api_key_label"))
        groq_key_label.grid(row=1, column=0, sticky="w", padx=10, pady=(2, 0))

        self._groq_key_entry = ctk.CTkEntry(groq_frame, show="*")
        self._groq_key_entry.grid(row=2, column=0, sticky="ew", padx=(10, 5), pady=2)

        self._groq_toggle_btn = ctk.CTkButton(
            groq_frame,
            text=i18n.t("ui.settings.show_key"),
            width=50,
            command=self._toggle_groq_key_visibility
        )
        self._groq_toggle_btn.grid(row=2, column=1, padx=(0, 10), pady=2)

        # Groq Model
        groq_model_label = ctk.CTkLabel(groq_frame, text=i18n.t("ui.settings.groq_model_label"))
        groq_model_label.grid(row=3, column=0, sticky="w", padx=10, pady=(5, 0))

        self._groq_model_combo = ctk.CTkComboBox(groq_frame, values=[config.GROQ_REVIEW_MODEL])
        self._groq_model_combo.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=2)

        # Fetch Models Button (centered under the API sections)
        self._fetch_models_btn = ctk.CTkButton(
            self._scroll_frame,
            text=i18n.t("ui.settings.fetch_models_btn"),
            command=self._async_fetch_models
        )
        self._fetch_models_btn.grid(row=2, column=0, padx=10, pady=5)

        # -------------------------------------------------------------------
        # Seção Rede
        # -------------------------------------------------------------------
        network_frame = ctk.CTkFrame(self._scroll_frame)
        network_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=10)
        network_frame.grid_columnconfigure(0, weight=1)

        net_title = ctk.CTkLabel(
            network_frame,
            text=i18n.t("ui.settings.network_section"),
            font=ctk.CTkFont(weight="bold", size=14)
        )
        net_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=10)

        # Host
        host_label = ctk.CTkLabel(network_frame, text=i18n.t("ui.settings.network_host_label"))
        host_label.grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self._host_entry = ctk.CTkEntry(network_frame)
        self._host_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=2)

        # Port
        port_label = ctk.CTkLabel(network_frame, text=i18n.t("ui.settings.network_port_label"))
        port_label.grid(row=2, column=0, sticky="w", padx=10, pady=2)
        self._port_entry = ctk.CTkEntry(network_frame)
        self._port_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=2)

        # Interval
        interval_label = ctk.CTkLabel(network_frame, text=i18n.t("ui.settings.network_interval_label"))
        interval_label.grid(row=3, column=0, sticky="w", padx=10, pady=2)
        self._interval_entry = ctk.CTkEntry(network_frame)
        self._interval_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=2)

        # -------------------------------------------------------------------
        # Seção Geral e Pastas
        # -------------------------------------------------------------------
        general_frame = ctk.CTkFrame(self._scroll_frame)
        general_frame.grid(row=4, column=0, sticky="ew", padx=5, pady=10)
        general_frame.grid_columnconfigure(1, weight=1)

        gen_title = ctk.CTkLabel(
            general_frame,
            text=i18n.t("ui.settings.general_section"),
            font=ctk.CTkFont(weight="bold", size=14)
        )
        gen_title.grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=10)

        # Language
        lang_label = ctk.CTkLabel(general_frame, text=i18n.t("ui.settings.lang_label"))
        lang_label.grid(row=1, column=0, sticky="w", padx=10, pady=5)
        self._lang_combo = ctk.CTkComboBox(general_frame, values=["pt", "en"], state="readonly")
        self._lang_combo.grid(row=1, column=1, columnspan=2, sticky="ew", padx=10, pady=5)

        # Vault Folder
        vault_label = ctk.CTkLabel(general_frame, text=i18n.t("ui.settings.vault_path_label"))
        vault_label.grid(row=2, column=0, sticky="w", padx=10, pady=2)
        self._vault_entry = ctk.CTkEntry(general_frame)
        self._vault_entry.grid(row=2, column=1, sticky="ew", padx=(10, 5), pady=2)
        self._vault_browse_btn = ctk.CTkButton(
            general_frame,
            text="...",
            width=30,
            command=lambda: self._browse_directory(self._vault_entry)
        )
        self._vault_browse_btn.grid(row=2, column=2, padx=(0, 10), pady=2)

        # Dual Folder
        dual_label = ctk.CTkLabel(general_frame, text=i18n.t("ui.settings.dual_path_label"))
        dual_label.grid(row=3, column=0, sticky="w", padx=10, pady=2)
        self._dual_entry = ctk.CTkEntry(general_frame)
        self._dual_entry.grid(row=3, column=1, sticky="ew", padx=(10, 5), pady=2)
        self._dual_browse_btn = ctk.CTkButton(
            general_frame,
            text="...",
            width=30,
            command=lambda: self._browse_directory(self._dual_entry)
        )
        self._dual_browse_btn.grid(row=3, column=2, padx=(0, 10), pady=2)

        # -------------------------------------------------------------------
        # Seção Alertas e Notificações (Silk style)
        # -------------------------------------------------------------------
        alerts_frame = ctk.CTkFrame(self._scroll_frame)
        alerts_frame.grid(row=5, column=0, sticky="ew", padx=5, pady=10)
        alerts_frame.grid_columnconfigure(1, weight=1)

        alerts_title = ctk.CTkLabel(
            alerts_frame,
            text=i18n.t("ui.settings.alerts_section"),
            font=ctk.CTkFont(weight="bold", size=14)
        )
        alerts_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=10)

        # Tray Integration Check
        from app.utils.tray_manager import PYS_AVAILABLE
        self._tray_enabled_var = ctk.BooleanVar()
        self._tray_switch = ctk.CTkSwitch(
            alerts_frame,
            text=i18n.t("ui.settings.tray_enabled_label"),
            variable=self._tray_enabled_var
        )
        self._tray_switch.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        
        if not PYS_AVAILABLE:
            self._tray_switch.configure(
                state="disabled",
                text=f"{i18n.t('ui.settings.tray_enabled_label')} ({i18n.t('ui.settings.tray_disabled_warning')})"
            )

        # Background Notifications Enable
        self._notifs_enabled_var = ctk.BooleanVar()
        self._notifs_switch = ctk.CTkSwitch(
            alerts_frame,
            text=i18n.t("ui.settings.notifications_enabled_label"),
            variable=self._notifs_enabled_var
        )
        self._notifs_switch.grid(row=2, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        # Reminder Interval Slider
        self._interval_label = ctk.CTkLabel(
            alerts_frame,
            text=i18n.t("ui.settings.alert_interval_label", minutes=15)
        )
        self._interval_label.grid(row=3, column=0, sticky="w", padx=10, pady=(5, 0))

        self._interval_slider = ctk.CTkSlider(
            alerts_frame,
            from_=1,
            to=60,
            number_of_steps=59,
            command=self._on_slider_change
        )
        self._interval_slider.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))

        # Audio Types Checklist
        types_label = ctk.CTkLabel(
            alerts_frame,
            text=i18n.t("ui.settings.alert_types_label")
        )
        types_label.grid(row=5, column=0, sticky="w", padx=10, pady=(5, 0))

        self._type_realtime_var = ctk.BooleanVar(value=True)
        self._type_realtime_check = ctk.CTkCheckBox(
            alerts_frame,
            text=i18n.t("ui.settings.alert_types_realtime"),
            variable=self._type_realtime_var
        )
        self._type_realtime_check.grid(row=6, column=0, sticky="w", padx=20, pady=2)

        self._type_file_var = ctk.BooleanVar(value=False)
        self._type_file_check = ctk.CTkCheckBox(
            alerts_frame,
            text=i18n.t("ui.settings.alert_types_file"),
            variable=self._type_file_var
        )
        self._type_file_check.grid(row=7, column=0, sticky="w", padx=20, pady=2)

        # -------------------------------------------------------------------
        # Action Buttons (Bottom Bar)
        # -------------------------------------------------------------------
        self._action_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        self._action_frame.grid(row=0, column=0, sticky="ew", pady=(0, 0))
        self._action_frame.place(relx=0.0, rely=1.0, anchor="sw", relwidth=1.0)
        self._action_frame.grid_columnconfigure(0, weight=1)
        self._action_frame.grid_columnconfigure(1, weight=1)

        self._save_btn = ctk.CTkButton(
            self._action_frame,
            text=i18n.t("ui.buttons.save"),
            fg_color="#2ca58d",  # Custom harmony color
            hover_color="#1f7d6a",
            command=self._save_settings
        )
        self._save_btn.grid(row=0, column=0, padx=20, pady=15, sticky="ew")

        self._cancel_btn = ctk.CTkButton(
            self._action_frame,
            text=i18n.t("ui.buttons.cancel"),
            fg_color="#ef5b5b",  # Custom harmony red
            hover_color="#c83f3f",
            command=self.destroy
        )
        self._cancel_btn.grid(row=0, column=1, padx=20, pady=15, sticky="ew")

    def _on_slider_change(self, val: float) -> None:
        minutes = int(val)
        self._interval_label.configure(
            text=i18n.t("ui.settings.alert_interval_label", minutes=minutes)
        )

    def _toggle_gemini_key_visibility(self) -> None:
        self._gemini_key_visible = not self._gemini_key_visible
        if self._gemini_key_visible:
            self._gemini_key_entry.configure(show="")
            self._gemini_toggle_btn.configure(text=i18n.t("ui.settings.hide_key"))
        else:
            self._gemini_key_entry.configure(show="*")
            self._gemini_toggle_btn.configure(text=i18n.t("ui.settings.show_key"))

    def _toggle_groq_key_visibility(self) -> None:
        self._groq_key_visible = not self._groq_key_visible
        if self._groq_key_visible:
            self._groq_key_entry.configure(show="")
            self._groq_toggle_btn.configure(text=i18n.t("ui.settings.hide_key"))
        else:
            self._groq_key_entry.configure(show="*")
            self._groq_toggle_btn.configure(text=i18n.t("ui.settings.show_key"))

    def _browse_directory(self, entry_widget: ctk.CTkEntry) -> None:
        current_dir = entry_widget.get().strip()
        dir_path = filedialog.askdirectory(initialdir=current_dir or None)
        if dir_path:
            entry_widget.delete(0, ctk.END)
            entry_widget.insert(0, dir_path)

    def _load_settings_into_ui(self) -> None:
        """Load currently stored configurations from the SQLite database."""
        # 1. API Keys (decrypt first)
        enc_gemini = db.get_setting("GOOGLE_API_KEY", "")
        gemini_key = sec.decrypt_value(enc_gemini) if enc_gemini else ""
        self._gemini_key_entry.insert(0, gemini_key)

        enc_groq = db.get_setting("GROQ_API_KEY", "")
        groq_key = sec.decrypt_value(enc_groq) if enc_groq else ""
        self._groq_key_entry.insert(0, groq_key)

        # 2. Models
        active_gemini_model = db.get_setting("GEMINI_MODEL", config.GEMINI_MODEL)
        self._gemini_model_combo.set(active_gemini_model)

        active_groq_model = db.get_setting("GROQ_REVIEW_MODEL", config.GROQ_REVIEW_MODEL)
        self._groq_model_combo.set(active_groq_model)

        # Populate combos with default options on load (in case fetch fails or wasn't run)
        # We merge defaults with currently selected to make sure selected is available
        self._gemini_model_combo.configure(
            values=sorted(list(set([active_gemini_model, "gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"])))
        )
        self._groq_model_combo.configure(
            values=sorted(list(set([active_groq_model, "llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768", "whisper-large-v3"])))
        )

        # 3. Network Configuration
        self._host_entry.insert(0, db.get_setting("NETWORK_PING_HOST", str(config.NETWORK_PING_HOST)))
        self._port_entry.insert(0, db.get_setting("NETWORK_PING_PORT", str(config.NETWORK_PING_PORT)))
        self._interval_entry.insert(0, db.get_setting("NETWORK_CHECK_INTERVAL", str(config.NETWORK_CHECK_INTERVAL)))

        # 4. General
        self._lang_combo.set(db.get_setting("APP_LANGUAGE", config.APP_LANGUAGE))
        
        # Strip project path prefix from DB values if they represent relative Vault paths
        vault_path = db.get_setting("VAULT_PATH", "Vault")
        self._vault_entry.insert(0, vault_path)

        dual_path = db.get_setting("DUAL_INTERMEDIARY_PATH", "DualRecordings")
        self._dual_entry.insert(0, dual_path)

        # 5. Alerts & Tray Config
        tray_enabled = db.get_setting("TRAY_ENABLED", "False").lower() == "true"
        self._tray_enabled_var.set(tray_enabled)

        notifs_enabled = db.get_setting("PERSISTENT_NOTIFICATIONS_ENABLED", "True").lower() == "true"
        self._notifs_enabled_var.set(notifs_enabled)

        alert_interval = int(db.get_setting("ALERT_INTERVAL", "15"))
        self._interval_slider.set(alert_interval)
        self._interval_label.configure(
            text=i18n.t("ui.settings.alert_interval_label", minutes=alert_interval)
        )

        alert_types = db.get_setting("ALERT_TRANSCRIPTION_TYPES", "realtime").split(",")
        self._type_realtime_var.set("realtime" in alert_types)
        self._type_file_var.set("file" in alert_types)

    def _async_fetch_models(self) -> None:
        """Call APIs asynchronously to fetch available models without blocking UI."""
        gemini_key = self._gemini_key_entry.get().strip()
        groq_key = self._groq_key_entry.get().strip()

        # Update button text to display loading state
        self._fetch_models_btn.configure(
            text=i18n.t("ui.settings.fetch_loading"),
            state="disabled"
        )

        def _worker():
            try:
                gemini_list = fetch_gemini_models(gemini_key)
                groq_list = fetch_groq_models(groq_key)

                # Update UI elements in Tkinter main thread
                self.after(0, lambda: self._update_model_combos(gemini_list, groq_list))
            except Exception as e:
                self.after(0, lambda: self._handle_fetch_error(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _update_model_combos(self, gemini_list: List[str], groq_list: List[str]) -> None:
        # Save current selections
        cur_gemini = self._gemini_model_combo.get()
        cur_groq = self._groq_model_combo.get()

        # Re-set values
        self._gemini_model_combo.configure(values=gemini_list)
        if cur_gemini in gemini_list:
            self._gemini_model_combo.set(cur_gemini)
        elif gemini_list:
            self._gemini_model_combo.set(gemini_list[0])

        self._groq_model_combo.configure(values=groq_list)
        if cur_groq in groq_list:
            self._groq_model_combo.set(cur_groq)
        elif groq_list:
            self._groq_model_combo.set(groq_list[0])

        # Restore fetch button state
        self._fetch_models_btn.configure(
            text=i18n.t("ui.settings.fetch_models_btn"),
            state="normal"
        )
        messagebox.showinfo(
            i18n.t("ui.settings.title"),
            i18n.t("ui.settings.fetch_success")
        )

    def _handle_fetch_error(self, err: Exception) -> None:
        self._fetch_models_btn.configure(
            text=i18n.t("ui.settings.fetch_models_btn"),
            state="normal"
        )
        messagebox.showerror(
            i18n.t("ui.settings.title"),
            f"{i18n.t('ui.settings.fetch_error')}\nDetails: {err}"
        )

    def _save_settings(self) -> None:
        """Validate, encrypt, and persist all settings into SQLite DB."""
        gemini_key = self._gemini_key_entry.get().strip()
        groq_key = self._groq_key_entry.get().strip()

        # Validation: check if fields are empty
        if not gemini_key or not groq_key:
            messagebox.showwarning(
                i18n.t("ui.settings.title"),
                "As chaves de API do Google Gemini e Groq são obrigatórias!"
            )
            return

        try:
            # 1. Encrypt API Keys
            enc_gemini = sec.encrypt_value(gemini_key)
            enc_groq = sec.encrypt_value(groq_key)

            # 2. Persist in database
            db.set_setting("GOOGLE_API_KEY", enc_gemini)
            db.set_setting("GROQ_API_KEY", enc_groq)

            db.set_setting("GEMINI_MODEL", self._gemini_model_combo.get())
            db.set_setting("GROQ_REVIEW_MODEL", self._groq_model_combo.get())

            db.set_setting("NETWORK_PING_HOST", self._host_entry.get().strip() or "8.8.8.8")
            db.set_setting("NETWORK_PING_PORT", self._port_entry.get().strip() or "53")
            db.set_setting("NETWORK_CHECK_INTERVAL", self._interval_entry.get().strip() or "10")

            db.set_setting("APP_LANGUAGE", self._lang_combo.get())
            db.set_setting("VAULT_PATH", self._vault_entry.get().strip() or "Vault")
            db.set_setting("DUAL_INTERMEDIARY_PATH", self._dual_entry.get().strip() or "DualRecordings")

            # Save Tray and Alerts configs
            db.set_setting("TRAY_ENABLED", str(self._tray_enabled_var.get()))
            db.set_setting("PERSISTENT_NOTIFICATIONS_ENABLED", str(self._notifs_enabled_var.get()))
            db.set_setting("ALERT_INTERVAL", str(int(self._interval_slider.get())))

            active_types = []
            if self._type_realtime_var.get():
                active_types.append("realtime")
            if self._type_file_var.get():
                active_types.append("file")
            db.set_setting("ALERT_TRANSCRIPTION_TYPES", ",".join(active_types))

            # 3. Reload config to apply settings in-memory immediately
            config.reload_config()

            messagebox.showinfo(
                i18n.t("ui.settings.title"),
                i18n.t("ui.settings.save_success")
            )

            # 4. Trigger callback if registered
            if self._on_saved:
                self._on_saved()

            self.destroy()

        except Exception as e:
            messagebox.showerror(
                i18n.t("ui.settings.title"),
                f"{i18n.t('ui.settings.save_error')}\nError: {e}"
            )
