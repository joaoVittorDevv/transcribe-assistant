"""app.ui.main_window — Primary application window.

Orchestrates all backend services (AudioRecorder, NetworkMonitor,
Transcriber) and UI sub-components (Sidebar, VUMeter, HistoryWindow)
into a single cohesive CustomTkinter interface.

Threading strategy:
  - Audio capture callback → Queue → root.after() polling → UI update
  - Transcription call    → dedicated Thread → Queue → root.after() polling
  - Network monitor       → daemon Thread   → callback → root.after()
"""

import queue
import threading
import time
from pathlib import Path

import customtkinter as ctk

import app.database as db
from app.audio_recorder import AudioRecorder
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
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Assistente de Transcrição")
        self.geometry("960x620")
        self.minsize(800, 500)

        # --- State ---
        self._current_session_id: int | None = None
        self._is_recording = False
        self._record_start_time: float | None = None
        self._rms_queue: queue.Queue[float] = queue.Queue()
        self._save_timer: str | None = None

        # --- Services ---
        self._recorder = AudioRecorder(on_rms_update=self._on_rms)
        self._network_monitor = NetworkMonitor(on_status_change=self._on_network_change)
        self._transcriber = Transcriber(
            is_online_fn=lambda: self._network_monitor.is_online
        )

        # --- Build UI ---
        self._build_layout()

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
            values=["Automático", "Google", "Whisper"],
            command=lambda _: None,
        )
        self._mode_selector.set("Automático")
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
            status_frame, text="Offline", font=("", 11), text_color="gray"
        )
        self._network_label.pack(side="left", padx=(0, 14))

        ctk.CTkButton(
            status_frame,
            text="📋 Histórico",
            width=110,
            command=self._open_history,
        ).pack(side="left")

    def _build_text_area(self, parent) -> None:
        """Editable transcription text area."""
        self._textbox = ctk.CTkTextbox(
            parent,
            font=("", 14),
            wrap="word",
            state="normal",
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        self._textbox.bind("<KeyRelease>", self._on_text_change)

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

        # Column 3 is already configured with weight=1 above — no widget needed

        # Action buttons (right side)
        btn_frame = ctk.CTkFrame(controls, fg_color="transparent")
        btn_frame.grid(row=0, column=4, sticky="e")

        self._record_btn = ctk.CTkButton(
            btn_frame,
            text="⏺  Gravar",
            width=130,
            height=42,
            font=("", 14, "bold"),
            fg_color="#dc2626",
            hover_color="#991b1b",
            command=self._toggle_recording,
        )
        self._record_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Copiar",
            width=90,
            command=self._copy_text,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_frame,
            text="Resetar",
            width=90,
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray20"),
            text_color=("gray10", "gray90"),
            command=self._reset_context,
        ).pack(side="left")

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
            text="⏸  Parar",
            fg_color="#16a34a",
            hover_color="#15803d",
        )
        self._status_label.configure(text="Gravando…", text_color="#22c55e")
        self._update_timer()

    def _stop_recording(self) -> None:
        self._is_recording = False
        self._record_btn.configure(state="disabled", text="Processando…")
        self._status_label.configure(
            text="Transcrevendo, aguarde…", text_color="#eab308"
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
        threading.Thread(
            target=self._transcribe_worker,
            args=(wav_path,),
            daemon=True,
            name="TranscribeWorker",
        ).start()

    def _transcribe_worker(self, wav_path: Path) -> None:
        """Run in the worker thread — posts result to the UI queue."""
        prompt_data = self._sidebar.get_active_prompt()
        prompt_text = prompt_data["texto_prompt"] if prompt_data else ""
        keywords = prompt_data["palavras_chave"] if prompt_data else []

        mode_map = {"Automático": "auto", "Google": "gemini", "Whisper": "whisper"}
        mode = mode_map.get(self._mode_selector.get(), "auto")

        # DEBUG - REMOVE LATER
        print(
            f"[DEBUG] TranscribeWorker: modo={mode} | prompt={bool(prompt_text)} | keywords={keywords}"
        )

        try:
            text = self._transcriber.transcribe(wav_path, prompt_text, keywords, mode)
            # DEBUG - REMOVE LATER
            print(
                f"[DEBUG] TranscribeWorker: texto recebido ({len(text)} chars): {text[:80]}..."
            )
            _ui_queue.put(("transcription_done", text))
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
            # Clean up the temporary WAV file
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

    def _finish_transcription_ok(self, text: str) -> None:
        if not text:
            text = "[Áudio sem conteúdo reconhecível]"

        self._insert_transcription(text)
        self._persist_full_session()
        self._restore_record_button()
        self._status_label.configure(
            text="✓ Transcrição concluída", text_color="#22c55e"
        )

    def _finish_transcription_error(self, message: str) -> None:
        # DEBUG - REMOVE LATER
        print(f"[DEBUG] MainWindow: erro de transcricao: {message}")
        self._restore_record_button()
        self._status_label.configure(
            text=f"Erro: {message}",
            text_color="#ef4444",
        )

    def _restore_record_button(self) -> None:
        self._record_btn.configure(
            state="normal",
            text="⏺  Gravar",
            fg_color="#dc2626",
            hover_color="#991b1b",
        )
        self._vu_meter.set_level(0.0)

    # ==================================================================
    # Text area helpers
    # ==================================================================

    def _insert_transcription(self, text: str) -> None:
        """Insert new transcription text at the current cursor position."""
        if not text:
            return

        cursor_idx = self._textbox.index("insert")

        # Smart spacing: add a space if the previous character isn't a space/newline
        # and we are not at the very beginning.
        prefix = ""
        if cursor_idx != "1.0":
            prev_char = self._textbox.get(f"{cursor_idx}-1c", cursor_idx)
            if prev_char and prev_char.strip():
                prefix = " "

        self._textbox.insert("insert", f"{prefix}{text}")
        self._textbox.see("insert")

    def _on_text_change(self, event=None) -> None:
        """Handle manual text edits with debounced auto-save."""
        if self._save_timer:
            self.after_cancel(self._save_timer)
        self._save_timer = self.after(1000, self._persist_full_session)

    def _get_full_text(self) -> str:
        return self._textbox.get("1.0", "end").strip()

    # ==================================================================
    # Database session management
    # ==================================================================

    def _persist_full_session(self) -> None:
        """Save the ENTIRE text content to the database."""
        self._save_timer = None
        full_text = self._get_full_text()

        if self._current_session_id is None:
            if full_text:  # Only create a new session if there is text
                self._current_session_id = db.create_session(full_text)
        else:
            # Update existing session (even if empty, to reflect deletions)
            db.overwrite_session_content(self._current_session_id, full_text)

    def _reset_context(self) -> None:
        """Clear the text area and detach from the current session."""
        self._current_session_id = None
        self._textbox.delete("1.0", "end")
        self._timer_label.configure(text="00:00")
        self._status_label.configure(text="Contexto reiniciado.", text_color="gray")

    def _restore_session(self, session_id: int, text: str) -> None:
        """Restore a historical session to the text area."""
        self._current_session_id = session_id
        self._textbox.delete("1.0", "end")
        self._textbox.insert("1.0", text)
        self._status_label.configure(
            text="Sessão restaurada — pronto para continuar.", text_color="#22c55e"
        )

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
        text = self._get_full_text()
        self.clipboard_clear()
        self.clipboard_append(text)
        self._status_label.configure(
            text="✓ Copiado para a área de transferência.", text_color="#22c55e"
        )

    def _open_history(self) -> None:
        HistoryWindow(self, on_restore=self._restore_session)

    # ==================================================================
    # Network status
    # ==================================================================

    def _on_network_change(self, is_online: bool) -> None:
        """Called from NetworkMonitor thread — posts to UI queue."""
        _ui_queue.put(("network_change", is_online))

    def _apply_network_status(self, is_online: bool) -> None:
        if is_online:
            self._network_dot.configure(text_color="#22c55e")
            self._network_label.configure(text="Online")
        else:
            self._network_dot.configure(text_color="#ef4444")
            self._network_label.configure(text="Offline")

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
