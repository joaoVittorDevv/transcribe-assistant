"""app.ui.main_window — Primary application window.

Orchestrates all backend services (AudioRecorder, NetworkMonitor,
Transcriber) and UI sub-components (Sidebar, VUMeter, HistoryWindow)
into a single cohesive CustomTkinter interface.

Threading strategy:
  - Audio capture callback → Queue → root.after() polling → UI update
  - Transcription call    → dedicated Thread → Queue → root.after() polling
  - Network monitor       → daemon Thread   → callback → root.after()
"""

import i18n
import queue
import threading
import time
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk

import app.database as db
from app.audio_recorder import AudioRecorder
from app.audio_validator import (
    AudioValidator,
    get_file_dialog_filetypes,
    is_supported_format,
)
from app.network_monitor import NetworkMonitor
from app.transcriber import Transcriber, TranscriptionError
from app.ui.history_window import HistoryWindow
from app.ui.sidebar import Sidebar
from app.ui.vu_meter import VUMeter

# Queue used to safely post events from worker threads to the UI thread
_ui_queue: queue.Queue = queue.Queue()

# Polling interval (ms) for the event queue
_POLL_MS = 100

# Timer update interval (ms)
_TIMER_MS = 500


class MainWindow(ctk.CTk):
    """Main application window for the Transcription Assistant."""

    def __init__(self) -> None:
        super().__init__(className="transcribe-assistant")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(i18n.t("ui.title"))
        self.geometry("960x620")
        self.minsize(800, 500)

        # --- Window Icon (taskbar + alt+tab) ---
        self._icon_photos: list[ImageTk.PhotoImage] = []
        icon_path = (
            Path(__file__).resolve().parent.parent.parent
            / "assets"
            / "assist_transcribe_1x1.png"
        )
        if icon_path.exists():
            icon_pil = Image.open(icon_path)
            for size in (16, 32, 48, 64, 128):
                resized = icon_pil.resize((size, size), Image.LANCZOS)
                self._icon_photos.append(ImageTk.PhotoImage(resized))
            self.iconphoto(True, *self._icon_photos)
            self.after(200, lambda: self.iconphoto(True, *self._icon_photos))

        # --- State ---
        self._tabs_data: dict[str, dict] = {}
        self._tab_count = 0
        self._active_tab: str | None = None
        self._is_recording = False
        self._record_start_time: float | None = None
        self._rms_queue: queue.Queue[float] = queue.Queue()
        self._save_timers: dict[str, str | None] = {}

        # --- Services ---
        self._recorder = AudioRecorder(on_rms_update=self._on_rms)
        self._network_monitor = NetworkMonitor(on_status_change=self._on_network_change)
        self._transcriber = Transcriber(
            is_online_fn=lambda: self._network_monitor.is_online
        )
        self._audio_validator = AudioValidator(
            is_online_fn=lambda: self._network_monitor.is_online
        )

        # --- Build UI ---
        self._build_layout()
        self.refresh_labels()

        # --- Start background services ---
        self._network_monitor.start()

        # --- Start UI event loops ---
        self._poll_ui_queue()
        self._poll_rms_queue()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ==================================================================
    # UI Layout
    # ==================================================================

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- Sidebar (left) ----
        self._sidebar = Sidebar(
            self,
            on_prompt_changed=lambda: None,  # No extra action needed
        )
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        # ---- Main area (right) ----
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self._build_top_bar(main)
        self._build_text_area(main)
        self._build_controls(main)

    def _build_top_bar(self, parent) -> None:
        """Top bar: mode selector + status indicators."""
        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        bar.grid_columnconfigure(1, weight=1)

        # Mode selector
        self._mode_selector = ctk.CTkSegmentedButton(
            bar,
            values=[
                i18n.t("ui.modes.automatic"),
                i18n.t("ui.modes.google"),
                i18n.t("ui.modes.whisper"),
            ],
            command=lambda _: None,
        )
        self._mode_selector.set(i18n.t("ui.modes.automatic"))
        self._mode_selector.grid(row=0, column=0, sticky="w")

        # Right-side status: network + history button
        status_frame = ctk.CTkFrame(bar, fg_color="transparent")
        status_frame.grid(row=0, column=2, sticky="e")

        self._network_dot = ctk.CTkLabel(
            status_frame,
            text="●",
            text_color="#ef4444",
            font=("", 18),
        )
        self._network_dot.pack(side="left", padx=(0, 6))

        self._network_label = ctk.CTkLabel(
            status_frame,
            text=i18n.t("ui.network.offline"),
            font=("", 11),
            text_color="gray",
        )
        self._network_label.pack(side="left", padx=(0, 14))

        # Language Toggle Button
        self._lang_btn = ctk.CTkSegmentedButton(
            status_frame,
            values=["PT", "EN"],
            command=self._set_language,
        )
        self._lang_btn.set("PT" if i18n.get("locale") == "pt" else "EN")
        self._lang_btn.pack(side="left", padx=(0, 10))

        # Import audio icon button (discrete, no label)
        self._import_btn = ctk.CTkButton(
            status_frame,
            text="📂",
            width=36,
            height=36,
            font=("", 16),
            fg_color="transparent",
            hover_color=("gray75", "gray30"),
            corner_radius=8,
            command=self._import_audio_file,
        )
        self._import_btn.pack(side="left", padx=(0, 6))

        # Tooltip for import button
        self._import_tooltip = _Tooltip(
            self._import_btn,
            text_fn=lambda: i18n.t("ui.buttons.import_audio"),
        )

        self._history_btn = ctk.CTkButton(
            status_frame,
            text=i18n.t("ui.buttons.history"),
            width=110,
            command=self._open_history,
        )
        self._history_btn.pack(side="left")

    def _build_text_area(self, parent) -> None:
        """Editable transcription text area with custom tabs."""
        wrapper = ctk.CTkFrame(parent, fg_color="transparent")
        wrapper.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        wrapper.grid_columnconfigure(0, weight=1)
        wrapper.grid_rowconfigure(1, weight=1)

        self._tabs_scroll = ctk.CTkScrollableFrame(
            wrapper,
            orientation="horizontal",
            height=45,
            fg_color="transparent",
            bg_color="transparent",
        )
        self._tabs_scroll.grid(row=0, column=0, sticky="ew")

        self._content_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
        self._content_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        self._new_tab_btn_top = ctk.CTkButton(
            self._tabs_scroll,
            text="+",
            width=30,
            height=28,
            fg_color="gray30",
            hover_color="gray40",
            command=self._cmd_new_tab,
        )

        self._add_new_tab("Nova Sessão 1")

    def _add_new_tab(
        self, name: str, session_id: int | None = None, content: str = ""
    ) -> None:
        # Ensure name uniqueness
        original_name = name
        counter = 1
        while name in self._tabs_data:
            name = f"{original_name} ({counter})"
            counter += 1

        # Tab Button Frame
        tab_frame = ctk.CTkFrame(self._tabs_scroll, fg_color="gray30", corner_radius=6)
        self._new_tab_btn_top.pack_forget()
        tab_frame.pack(side="left", padx=(0, 6), pady=4)

        tab_btn = ctk.CTkButton(
            tab_frame,
            text=name,
            fg_color="transparent",
            hover_color="gray40",
            corner_radius=6,
            height=28,
            command=lambda n=name: self._select_tab(n),
        )
        tab_btn.pack(side="left", padx=(2, 0))

        tab_btn.bind("<Button-2>", lambda e, n=name: self._cmd_rename_tab(n))
        tab_btn.bind("<Button-3>", lambda e, n=name: self._cmd_rename_tab(n))

        close_btn = ctk.CTkButton(
            tab_frame,
            text="×",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#ef4444",
            corner_radius=6,
            command=lambda n=name: self._cmd_close_tab(n),
        )
        close_btn.pack(side="left", padx=(0, 2))

        self._new_tab_btn_top.pack(side="left", padx=(0, 4), pady=4)

        textbox = ctk.CTkTextbox(
            self._content_frame,
            font=("", 14),
            wrap="word",
            state="normal",
        )
        textbox.grid(row=0, column=0, sticky="nsew", pady=0)
        textbox.insert("1.0", content)
        textbox.bind(
            "<KeyRelease>", lambda event, t=name: self._on_text_change(t, event)
        )

        self._tabs_data[name] = {
            "textbox": textbox,
            "session_id": session_id,
            "tab_frame": tab_frame,
            "tab_btn": tab_btn,
            "close_btn": close_btn,
        }
        self._save_timers[name] = None
        self._select_tab(name)

    def _select_tab(self, name: str) -> None:
        if self._active_tab == name:
            return

        if self._active_tab and self._active_tab in self._tabs_data:
            old_data = self._tabs_data[self._active_tab]
            old_data["textbox"].grid_remove()
            old_data["tab_frame"].configure(fg_color="gray30")
            old_data["tab_btn"].configure(text_color="gray80")

        self._active_tab = name
        new_data = self._tabs_data[name]
        new_data["textbox"].grid()
        new_data["tab_frame"].configure(fg_color="#1f6aa5")
        new_data["tab_btn"].configure(text_color="white")

    def _get_active_tab_data(self) -> dict | None:
        if self._active_tab:
            return self._tabs_data.get(self._active_tab)
        return None

    def _build_controls(self, parent) -> None:
        """Bottom controls: timer, VU meter, record button, copy, reset."""
        controls = ctk.CTkFrame(parent, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew")
        # Column 3 acts as a flexible spacer between status label and buttons
        controls.grid_columnconfigure(3, weight=1)

        # Timer
        self._timer_label = ctk.CTkLabel(
            controls,
            text="00:00",
            font=("", 22, "bold"),
            width=70,
        )
        self._timer_label.grid(row=0, column=0, padx=(0, 12))

        # VU Meter
        self._vu_meter = VUMeter(controls, width=28, height=50)
        self._vu_meter.grid(row=0, column=1, sticky="w", padx=(0, 16))

        # Status label (shows transcription progress)
        self._status_label = ctk.CTkLabel(
            controls, text="", font=("", 11), text_color="gray"
        )
        self._status_label.grid(row=0, column=2, sticky="w")

        # Column 3 acts as a flexible spacer between status label and buttons
        controls.grid_columnconfigure(3, weight=1)

        # Action buttons (right side)
        btn_frame = ctk.CTkFrame(controls, fg_color="transparent")
        btn_frame.grid(row=0, column=4, sticky="e")

        self._record_btn = ctk.CTkButton(
            btn_frame,
            text=i18n.t("ui.buttons.record"),
            width=130,
            height=42,
            font=("", 14, "bold"),
            fg_color="#dc2626",
            hover_color="#991b1b",
            command=self._toggle_recording,
        )

        self._cancel_btn = ctk.CTkButton(
            btn_frame,
            text=i18n.t("ui.buttons.cancel"),
            width=90,
            height=42,
            font=("", 14, "bold"),
            fg_color="#4b5563",
            hover_color="#374151",
            command=self._cancel_recording,
        )

        self._record_btn.pack(side="left", padx=(0, 8))

        self._copy_btn = ctk.CTkButton(
            btn_frame,
            text=i18n.t("ui.buttons.copy"),
            width=90,
            command=self._copy_text,
        )
        self._copy_btn.pack(side="left", padx=(0, 8))

        self._reset_btn = ctk.CTkButton(
            btn_frame,
            text=i18n.t("ui.buttons.reset"),
            width=90,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray20"),
            text_color=("gray10", "gray90"),
            command=self._reset_context,
        )
        self._reset_btn.pack(side="left")

    # ==================================================================
    # Localize (i18n)
    # ==================================================================

    def refresh_labels(self) -> None:
        """Update all text in the UI to match the current language."""
        self.title(i18n.t("ui.title"))
        current_mode_idx = 0
        try:
            current_idx_val = self._mode_selector.get()
            modes_pt = ["Automático", "Google", "Whisper"]
            modes_en = ["Automatic", "Google", "Whisper"]
            if current_idx_val in modes_pt:
                current_mode_idx = modes_pt.index(current_idx_val)
            elif current_idx_val in modes_en:
                current_mode_idx = modes_en.index(current_idx_val)
        except ValueError:
            pass

        new_modes = [
            i18n.t("ui.modes.automatic"),
            i18n.t("ui.modes.google"),
            i18n.t("ui.modes.whisper"),
        ]
        self._mode_selector.configure(values=new_modes)
        self._mode_selector.set(new_modes[current_mode_idx])

        self._history_btn.configure(text=i18n.t("ui.buttons.history"))
        self._copy_btn.configure(text=i18n.t("ui.buttons.copy"))
        self._reset_btn.configure(text=i18n.t("ui.buttons.reset"))

        if self._is_recording:
            self._record_btn.configure(text=i18n.t("ui.buttons.transcribe"))
            self._status_label.configure(text=i18n.t("ui.status.recording"))
        else:
            if "Transcrevendo" in str(
                self._status_label.cget("text")
            ) or "Transcribing" in str(self._status_label.cget("text")):
                self._record_btn.configure(text=i18n.t("ui.status.processing"))
                self._status_label.configure(text=i18n.t("ui.status.transcribing"))
            else:
                self._record_btn.configure(text=i18n.t("ui.buttons.record"))

        if self._network_monitor.is_online:
            self._network_label.configure(text=i18n.t("ui.network.online"))
        else:
            self._network_label.configure(text=i18n.t("ui.network.offline"))

        self._lang_btn.set("PT" if i18n.get("locale") == "pt" else "EN")

        self._sidebar.refresh_labels()

    def _set_language(self, language: str) -> None:
        """Switch language between PT and EN and refresh the UI."""
        new_lang = "pt" if language == "PT" else "en"
        if i18n.get("locale") != new_lang:
            i18n.set("locale", new_lang)
            self.refresh_labels()

    # ==================================================================
    # Recording flow
    # ==================================================================

    def _toggle_recording(self) -> None:
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self._is_recording = True
        self._record_start_time = time.time()
        self._recorder.start_recording()

        # DEBUG - REMOVE LATER
        print("[DEBUG] MainWindow: gravacao iniciada")

        self._record_btn.configure(
            text=i18n.t("ui.buttons.transcribe"),
            fg_color="#16a34a",
            hover_color="#15803d",
        )
        self._cancel_btn.pack(side="left", padx=(0, 8), before=self._copy_btn)

        self._status_label.configure(
            text=i18n.t("ui.status.recording"), text_color="#22c55e"
        )
        self._update_timer()

    def _stop_recording(self) -> None:
        self._is_recording = False
        self._cancel_btn.pack_forget()

        self._record_btn.configure(
            state="disabled", text=i18n.t("ui.status.processing")
        )
        self._status_label.configure(
            text=i18n.t("ui.status.transcribing"), text_color="#eab308"
        )

        # DEBUG - REMOVE LATER
        print("[DEBUG] MainWindow: gravacao parada, iniciando transcricao")

        try:
            wav_path = self._recorder.stop_recording()
        except RuntimeError as exc:
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] MainWindow: erro ao parar gravacao: {exc}")
            self._finish_transcription_error(str(exc))
            return

        # DEBUG - REMOVE LATER
        print(f"[DEBUG] MainWindow: audio salvo em {wav_path}")

        # Run transcription in a background thread
        active_tab = self._active_tab
        threading.Thread(
            target=self._transcribe_worker,
            args=(wav_path, active_tab),
            daemon=True,
            name="TranscribeWorker",
        ).start()

    def _cancel_recording(self) -> None:
        self._is_recording = False
        self._cancel_btn.pack_forget()

        # DEBUG - REMOVE LATER
        print("[DEBUG] MainWindow: gravacao cancelada")

        try:
            wav_path = self._recorder.stop_recording()
            try:
                wav_path.unlink(missing_ok=True)
            except OSError:
                pass
        except RuntimeError:
            pass

        self._restore_record_button()
        self._status_label.configure(
            text=i18n.t("ui.status.context_reset"), text_color="gray"
        )
        self._update_timer()
        self._timer_label.configure(text="00:00")

    def _transcribe_worker(
        self, wav_path: Path, target_tab_name: str, is_imported: bool = False
    ) -> None:
        """Run in the worker thread — posts result to the UI queue."""
        prompt_data = self._sidebar.get_active_prompt()
        prompt_text = prompt_data["texto_prompt"] if prompt_data else ""
        keywords = prompt_data["palavras_chave"] if prompt_data else []

        mode_map = {
            i18n.t("ui.modes.automatic"): "auto",
            i18n.t("ui.modes.google"): "gemini",
            i18n.t("ui.modes.whisper"): "whisper",
        }

        mode = mode_map.get(self._mode_selector.get(), "auto")

        # DEBUG - REMOVE LATER
        print(
            f"[DEBUG] TranscribeWorker: modo={mode} | prompt={bool(prompt_text)} | keywords={keywords} | imported={is_imported}"
        )

        try:
            text = self._transcriber.transcribe(wav_path, prompt_text, keywords, mode)
            # Generate title if session is completely new for this tab
            tab_data = self._tabs_data.get(target_tab_name)
            generated_title = None
            if tab_data and tab_data.get("session_id") is None:
                generated_title = self._transcriber.generate_title(text)

            _ui_queue.put(
                ("transcription_done", (text, target_tab_name, generated_title))
            )
        except TranscriptionError as exc:
            # DEBUG - REMOVE LATER
            print(f"[DEBUG] TranscribeWorker: TranscriptionError: {exc}")
            _ui_queue.put(("transcription_error", str(exc)))
        except Exception as exc:  # noqa: BLE001
            # DEBUG - REMOVE LATER
            print(
                f"[DEBUG] TranscribeWorker: erro inesperado: {type(exc).__name__}: {exc}"
            )
            _ui_queue.put(("transcription_error", f"{type(exc).__name__}: {exc}"))
        finally:
            # Only delete temporary files from mic recordings, not imported files
            if not is_imported:
                try:
                    wav_path.unlink(missing_ok=True)
                except OSError:
                    pass

    # ==================================================================
    # UI event queue (thread-safe UI updates)
    # ==================================================================

    def _poll_ui_queue(self) -> None:
        """Drain the UI event queue and reschedule itself."""
        try:
            while True:
                event, payload = _ui_queue.get_nowait()
                if event == "transcription_done":
                    self._finish_transcription_ok(payload)
                elif event == "transcription_error":
                    self._finish_transcription_error(payload)
                elif event == "network_change":
                    self._apply_network_status(payload)
                elif event == "import_rejected":
                    self._finish_import_rejected(payload)
                elif event == "import_accepted":
                    self._finish_import_accepted()
        except queue.Empty:
            pass
        self.after(_POLL_MS, self._poll_ui_queue)

    def _poll_rms_queue(self) -> None:
        """Drain the RMS queue and update the VU meter."""
        try:
            while True:
                level = self._rms_queue.get_nowait()
                self._vu_meter.set_level(level)
        except queue.Empty:
            pass
        self.after(_POLL_MS, self._poll_rms_queue)

    # ==================================================================
    # Transcription result handlers
    # ==================================================================

    def _finish_transcription_ok(self, payload: tuple[str, str, str | None]) -> None:
        text, target_tab, new_title = payload
        if not text:
            text = i18n.t("ui.status.audio_empty")

        self._insert_transcription(text, target_tab)
        self._persist_full_session(target_tab)

        if new_title:
            self._rename_tab_internally(target_tab, new_title)

        self._restore_record_button()
        self._status_label.configure(
            text=i18n.t("ui.status.transcription_done"), text_color="#22c55e"
        )

    def _finish_transcription_error(self, message: str) -> None:
        # DEBUG - REMOVE LATER
        print(f"[DEBUG] MainWindow: erro de transcricao: {message}")
        self._restore_record_button()
        self._status_label.configure(
            text=i18n.t("ui.status.error", message=message),
            text_color="#ef4444",
        )

    def _restore_record_button(self) -> None:
        self._record_btn.configure(
            state="normal",
            text=i18n.t("ui.buttons.record"),
            fg_color="#dc2626",
            hover_color="#991b1b",
        )
        self._import_btn.configure(state="normal")
        self._vu_meter.set_level(0.0)

    def _finish_import_rejected(self, reason: str) -> None:
        """Handle rejected audio import."""
        self._restore_record_button()
        self._status_label.configure(
            text=i18n.t("ui.status.audio_rejected", reason=reason),
            text_color="#ef4444",
        )

    def _finish_import_accepted(self) -> None:
        """Handle accepted audio import — transcription starts."""
        self._status_label.configure(
            text=i18n.t("ui.status.audio_accepted"), text_color="#eab308"
        )
        self._record_btn.configure(
            state="disabled", text=i18n.t("ui.status.processing")
        )

    # ==================================================================
    # Text area helpers
    # ==================================================================

    def _insert_transcription(self, text: str, target_tab: str | None = None) -> None:
        """Insert new transcription text at the current cursor position."""
        if not text:
            return

        tab_name = target_tab or self._active_tab
        if not tab_name:
            return
        tab_data = self._tabs_data.get(tab_name)
        if not tab_data:
            return

        textbox = tab_data["textbox"]
        cursor_idx = textbox.index("insert")

        # Smart spacing: add a space if the previous character isn't a space/newline
        # and we are not at the very beginning.
        prefix = ""
        if cursor_idx != "1.0":
            prev_char = textbox.get(f"{cursor_idx}-1c", cursor_idx)
            if prev_char and prev_char.strip():
                prefix = " "

        textbox.insert("insert", f"{prefix}{text}")
        textbox.see("insert")

    def _on_text_change(self, tab_name: str, event=None) -> None:
        """Handle manual text edits with debounced auto-save."""
        if self._save_timers.get(tab_name):
            self.after_cancel(self._save_timers[tab_name])

        timer_id = self.after(1000, lambda t=tab_name: self._persist_full_session(t))
        self._save_timers[tab_name] = timer_id

    def _get_full_text(self, tab_name: str) -> str:
        tab_data = self._tabs_data.get(tab_name)
        if not tab_data:
            return ""
        return tab_data["textbox"].get("1.0", "end").strip()

    # ==================================================================
    # Database session management
    # ==================================================================

    def _persist_full_session(self, tab_name: str | None = None) -> None:
        """Save the ENTIRE text content to the database."""
        if not tab_name:
            tab_name = self._active_tab
        if not tab_name:
            return

        self._save_timers[tab_name] = None
        full_text = self._get_full_text(tab_name)
        tab_data = self._tabs_data.get(tab_name)
        if not tab_data:
            return

        session_id = tab_data["session_id"]

        if session_id is None:
            if full_text:  # Only create a new session if there is text
                new_id = db.create_session(full_text, titulo=tab_name)
                tab_data["session_id"] = new_id
        else:
            # Update existing session (even if empty, to reflect deletions)
            db.overwrite_session_content(session_id, full_text)

    def _reset_context(self) -> None:
        """Clear the text area and detach from the current session."""
        active_tab = self._active_tab
        if not active_tab:
            return

        tab_data = self._tabs_data.get(active_tab)
        if not tab_data:
            return

        tab_data["session_id"] = None
        tab_data["textbox"].delete("1.0", "end")

        self._timer_label.configure(text="00:00")
        self._status_label.configure(
            text=i18n.t("ui.status.context_reset"), text_color="gray"
        )

    def _restore_session(self, session_id: int, text: str) -> None:
        """Restore a historical session to a new tab."""
        session_data = db.get_session_by_id(session_id)
        if not session_data:
            return

        title = session_data["titulo"]
        self._add_new_tab(name=title, session_id=session_id, content=text)
        self._status_label.configure(
            text=i18n.t("ui.status.session_restored"), text_color="#22c55e"
        )

    def _cmd_new_tab(self) -> None:
        self._tab_count += 1
        self._add_new_tab(f"Nova Sessão {self._tab_count + 1}")

    def _cmd_close_tab(self, tab_name: str | None = None) -> None:
        if tab_name is None:
            tab_name = self._active_tab
        if not tab_name:
            return

        # Ensure it's persisted first
        self._persist_full_session(tab_name)

        tab_data = self._tabs_data.pop(tab_name, None)
        self._save_timers.pop(tab_name, None)

        if tab_data:
            tab_data["tab_frame"].destroy()
            tab_data["textbox"].destroy()

        if self._active_tab == tab_name:
            self._active_tab = None
            if self._tabs_data:
                # select the first available tab
                self._select_tab(next(iter(self._tabs_data)))
            else:
                self._cmd_new_tab()

    def _cmd_rename_tab(self, tab_name: str | None = None) -> None:
        if tab_name is None:
            tab_name = self._active_tab
        if not tab_name:
            return

        # Wait for the context menu to close if it was a right click
        self.update_idletasks()

        dialog = ctk.CTkInputDialog(
            text=i18n.t("ui.buttons.rename_prompt"),
            title=i18n.t("ui.buttons.rename_title"),
        )
        new_name = dialog.get_input()

        if new_name and new_name.strip() and new_name.strip() != tab_name:
            self._rename_tab_internally(tab_name, new_name.strip())

    def _rename_tab_internally(self, old_name: str, new_name: str) -> None:
        if new_name in self._tabs_data:
            return  # Must be unique

        tab_data = self._tabs_data.pop(old_name)
        save_timer = self._save_timers.pop(old_name, None)

        session_id = tab_data["session_id"]

        # We simply reconfigure the existing components instead of deleting them
        tab_data["tab_btn"].configure(
            text=new_name, command=lambda n=new_name: self._select_tab(n)
        )
        tab_data["tab_btn"].bind(
            "<Button-2>", lambda e, n=new_name: self._cmd_rename_tab(n)
        )
        tab_data["tab_btn"].bind(
            "<Button-3>", lambda e, n=new_name: self._cmd_rename_tab(n)
        )
        tab_data["close_btn"].configure(
            command=lambda n=new_name: self._cmd_close_tab(n)
        )

        # Debounce timer needs the new tab name
        tab_data["textbox"].bind(
            "<KeyRelease>", lambda event, t=new_name: self._on_text_change(t, event)
        )

        self._tabs_data[new_name] = tab_data
        self._save_timers[new_name] = save_timer

        if self._active_tab == old_name:
            self._active_tab = new_name

        # Update db
        if session_id is not None:
            db.update_session_title(session_id, new_name)

    # ==================================================================
    # Timer
    # ==================================================================

    def _update_timer(self) -> None:
        if not self._is_recording or self._record_start_time is None:
            return
        elapsed = int(time.time() - self._record_start_time)
        minutes, seconds = divmod(elapsed, 60)
        self._timer_label.configure(text=f"{minutes:02d}:{seconds:02d}")
        self.after(_TIMER_MS, self._update_timer)

    # ==================================================================
    # Action buttons
    # ==================================================================

    def _copy_text(self) -> None:
        active_tab = self._active_tab
        if not active_tab:
            return
        text = self._get_full_text(active_tab)

        self.clipboard_clear()
        if text:
            self.clipboard_append(text)
            self._status_label.configure(
                text=i18n.t("ui.status.copied"), text_color="#22c55e"
            )

    def _open_history(self) -> None:
        HistoryWindow(self, on_restore=self._restore_session)

    # ==================================================================
    # Audio file import
    # ==================================================================

    def _import_audio_file(self) -> None:
        """Open file dialog to select an audio file for transcription."""
        if self._is_recording:
            return  # Don't import while recording

        filetypes = get_file_dialog_filetypes()
        file_path = filedialog.askopenfilename(
            title=i18n.t("ui.file_dialog.title"),
            filetypes=filetypes,
        )

        if not file_path:
            return  # User cancelled

        audio_path = Path(file_path)

        if not is_supported_format(audio_path):
            self._status_label.configure(
                text=i18n.t(
                    "ui.status.audio_rejected",
                    reason=f"Formato não suportado: {audio_path.suffix}",
                ),
                text_color="#ef4444",
            )
            return

        # Disable controls during import
        self._record_btn.configure(state="disabled")
        self._import_btn.configure(state="disabled")
        self._status_label.configure(
            text=i18n.t("ui.status.validating_audio"), text_color="#eab308"
        )

        active_tab = self._active_tab
        threading.Thread(
            target=self._import_worker,
            args=(audio_path, active_tab),
            daemon=True,
            name="ImportWorker",
        ).start()

    def _import_worker(self, audio_path: Path, target_tab_name: str) -> None:
        """Validate and transcribe an imported audio file (runs in thread)."""
        try:
            result = self._audio_validator.validate(audio_path)
            print(
                f"[DEBUG] ImportWorker: validation={result.is_valid} "
                f"confidence={result.confidence} reason={result.reason}"
            )

            if not result.is_valid:
                _ui_queue.put(
                    (
                        "import_rejected",
                        result.reason,
                    )
                )
                return

            # Validation passed — post acceptance and start transcription
            _ui_queue.put(("import_accepted", None))
            self._transcribe_worker(audio_path, target_tab_name, is_imported=True)

        except Exception as exc:  # noqa: BLE001
            print(f"[DEBUG] ImportWorker: erro: {exc}")
            _ui_queue.put(("transcription_error", f"Import error: {exc}"))

    # ==================================================================
    # Network status
    # ==================================================================

    def _on_network_change(self, is_online: bool) -> None:
        """Called from NetworkMonitor thread — posts to UI queue."""
        _ui_queue.put(("network_change", is_online))

    def _apply_network_status(self, is_online: bool) -> None:
        if is_online:
            self._network_dot.configure(text_color="#22c55e")
            self._network_label.configure(text=i18n.t("ui.network.online"))
        else:
            self._network_dot.configure(text_color="#ef4444")
            self._network_label.configure(text=i18n.t("ui.network.offline"))

    # ==================================================================
    # RMS callback (called from audio thread)
    # ==================================================================

    def _on_rms(self, level: float) -> None:
        """Thread-safe: audio callback posts RMS to queue."""
        try:
            self._rms_queue.put_nowait(level)
        except queue.Full:
            pass  # Drop if queue is full — VU meter is best-effort

    # ==================================================================
    # App lifecycle
    # ==================================================================

    def _on_close(self) -> None:
        if self._is_recording:
            self._recorder.stop_recording()
        self._network_monitor.stop()
        self.destroy()


# ======================================================================
# Tooltip helper (no external dependencies)
# ======================================================================


class _Tooltip:
    """Lightweight tooltip that appears on hover after a short delay.

    Args:
        widget:  The widget to attach the tooltip to.
        text_fn: A callable returning the tooltip text (supports i18n).
        delay:   Milliseconds before the tooltip appears.
    """

    _DELAY_MS = 500
    _PAD_X = 8
    _PAD_Y = 4

    def __init__(
        self,
        widget: ctk.CTkBaseClass,
        text_fn: callable,
        delay: int = _DELAY_MS,
    ) -> None:
        self._widget = widget
        self._text_fn = text_fn
        self._delay = delay
        self._tip_window: ctk.CTkToplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event=None) -> None:
        self._cancel()
        self._after_id = self._widget.after(self._delay, self._show)

    def _on_leave(self, _event=None) -> None:
        self._cancel()
        self._hide()

    def _cancel(self) -> None:
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self) -> None:
        if self._tip_window:
            return

        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4

        self._tip_window = tw = ctk.CTkToplevel(self._widget)
        tw.withdraw()
        tw.overrideredirect(True)

        label = ctk.CTkLabel(
            tw,
            text=self._text_fn(),
            font=("", 11),
            fg_color=("gray85", "gray20"),
            corner_radius=6,
            padx=self._PAD_X,
            pady=self._PAD_Y,
        )
        label.pack()

        tw.update_idletasks()
        tw.geometry(f"+{x}+{y}")
        tw.deiconify()

    def _hide(self) -> None:
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None
