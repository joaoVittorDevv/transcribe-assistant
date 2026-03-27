"""app.ui_flet.main_app — Interface principal do Flet (Async).

Orquestra todos os serviços de backend (AudioRecorder, NetworkMonitor,
TranscriberAgent) e componentes de UI (Sidebar, TabManager, VUMeter).

Estratégia de Threading/Async:
  - Captura de áudio       → sounddevice callback → on_rms → VU Meter
  - Salvamento WAV         → asyncio.to_thread (não bloqueia UI)
  - Upload Files API       → asyncio.to_thread (não bloqueia UI)
  - Stream da transcrição  → async for event in agent.arun(stream=True)
  - Atualização de UI      → throttled a cada 100ms via flush_update()
"""

import asyncio
import os
import time
import threading
from pathlib import Path

import flet as ft

from app.audio_recorder import AudioRecorder
from app.network_monitor import NetworkMonitor
from app.ui_flet.sidebar import Sidebar
from app.ui_flet.tab_manager import TabManager
from app.utils.i18n_manager import i18n
from app.ui.native_dialog import open_audio_file
from app.audio_validator import SUPPORTED_AUDIO_EXTENSIONS


class FletApp(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.expand = True
        self._page = page

        # --- Serviços (Backend) ---
        self._network_monitor = NetworkMonitor(on_status_change=self._on_network_change)
        self._recorder = AudioRecorder(on_rms_update=self._on_rms)
        self._network_monitor.start()

        # --- State ---
        self._is_recording = False
        self._current_audio_path: str | None = None
        self._current_request_id: int = 0
        self._active_task: asyncio.Task | None = None
        self._record_start_time: float | None = None
        self._timer_running = False

        self._build_ui()

    def _on_network_change(self, status):
        pass  # To do: update network indicator visual

    def _on_rms(self, level):
        self.vu_meter.set_level(level)

    def _on_audio_mode_change(self, e):
        mode = self.audio_mode_menu.value
        self.record_btn.custom_mode = mode
        if mode == "system":
            self.record_btn.bgcolor = "#b91c1c"
        else:
            self.record_btn.bgcolor = ft.Colors.RED_700
        try:
            self.record_btn.update()
        except Exception:
            pass

    def _copy_text(self, e):
        active = self.editor.active_tab
        text = active.get_text() if active is not None else ""
        if text:
            self.page.set_clipboard(text)
            self.status_label.value = "Texto copiado!"
            self.status_label.color = ft.Colors.GREEN
            try:
                self.status_label.update()
            except Exception:
                pass

    def _on_history_restore(self, session_id: str, texto: str) -> None:
        active = self.editor.active_tab
        if active is not None:
            active._body.value = texto
            active._first_insert = False
            try:
                active._body.update()
            except Exception:
                pass

    def _open_file_picker(self, e: ft.ControlEvent) -> None:
        """Abre o seletor nativo de arquivos de áudio."""
        file_path = open_audio_file(
            title=i18n.get("select_file"), extensions=SUPPORTED_AUDIO_EXTENSIONS
        )

        if file_path:
            self._current_audio_path = file_path
            self.status_label.value = f"Arquivo: {os.path.basename(file_path)}"
            self.status_label.color = ft.Colors.BLUE_400
            self.record_btn.content.value = i18n.get("transcribe")
            self.record_btn.bgcolor = ft.Colors.BLUE_700
            try:
                self.status_label.update()
                self.record_btn.update()
            except Exception:
                pass

    def _clear_text(self, e) -> None:
        active = self.editor.active_tab
        if active is not None:
            active.clear()

    def _build_ui(self) -> None:
        # Componentes Filhos
        self.sidebar = Sidebar()
        self.editor = TabManager(self._page)
        self.editor.add_tab()

        # Header Top Bar
        from app.ui_flet.history_window import HistoryModal

        self.history_btn = ft.ElevatedButton(
            i18n.get("history"),
            icon=ft.Icons.HISTORY,
            bgcolor="#4b5563",
            color="white",
            on_click=lambda e: HistoryModal(
                self.page, on_restore=self._on_history_restore
            ).show(),
        )

        self.app_title_text = ft.Text(
            i18n.get("app_title"), size=24, weight=ft.FontWeight.BOLD
        )
        self.online_status = ft.Text(i18n.get("online"), color=ft.Colors.GREEN)

        # Toggle de Idioma PT/EN
        self.lang_toggle = ft.SegmentedButton(
            selected=["pt"],
            segments=[
                ft.Segment(value="pt", label=ft.Text("PT", size=11, weight="bold")),
                ft.Segment(value="en", label=ft.Text("EN", size=11, weight="bold")),
            ],
            on_change=self._on_language_change,
            show_selected_icon=False,
            height=30,
        )

        # Botão Upload
        self.upload_btn = ft.IconButton(
            icon=ft.Icons.ATTACH_FILE_ROUNDED,
            icon_color=ft.Colors.GREY_400,
            tooltip=i18n.get("upload"),
            on_click=self._open_file_picker,
        )

        header = ft.Row(
            controls=[
                self.app_title_text,
                ft.Container(expand=True),
                self.lang_toggle,
                self.upload_btn,
                ft.VerticalDivider(width=10),
                self.history_btn,
                self.online_status,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # Controles Inferiores
        self.timer_label = ft.Text("00:00", size=24, weight=ft.FontWeight.BOLD)
        from app.ui_flet.vu_meter import VuMeter

        self.vu_meter = VuMeter(num_leds=20, led_width=7, led_height=18, spacing=2)

        self.model_selector = ft.Dropdown(
            options=[
                ft.dropdown.Option("Auto"),
                ft.dropdown.Option("Google Gemini"),
                ft.dropdown.Option("Whisper"),
            ],
            value="Auto",
            width=140,
            text_size=12,
            height=45,
        )

        self.audio_mode_menu = ft.Dropdown(
            options=[
                ft.dropdown.Option("mic", text="🎙️"),
                ft.dropdown.Option("system", text="🎧"),
            ],
            value="mic",
            width=60,
            text_size=16,
            height=45,
            on_select=self._on_audio_mode_change,
        )

        self.btn_area = ft.Row(spacing=5)

        self.record_btn = ft.Button(
            content=ft.Text(i18n.get("record"), weight=ft.FontWeight.BOLD),
            icon=ft.Icons.MIC_NONE,
            on_click=self._toggle_recording,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE,
            height=45,
        )
        self.record_btn.custom_mode = "mic"

        self.cancel_btn = ft.Button(
            content=ft.Text(i18n.get("cancel")),
            on_click=self._cancel_recording,
            bgcolor="#4b5563",
            color=ft.Colors.WHITE,
            height=45,
            visible=False,
        )

        self.copy_btn = ft.Button(
            content=ft.Text(i18n.get("copy")),
            icon=ft.Icons.COPY,
            on_click=self._copy_text,
            height=45,
        )

        self.reset_btn = ft.Button(
            content=ft.Text(i18n.get("clear")),
            icon=ft.Icons.DELETE_OUTLINE,
            on_click=self._clear_text,
            height=45,
        )

        self.btn_area.controls = [
            self.record_btn,
            self.cancel_btn,
            self.copy_btn,
            self.reset_btn,
        ]

        self.status_label = ft.Text(i18n.get("ready"), color="#9ca3af", size=12)

        actions = ft.Row(
            controls=[
                self.timer_label,
                self.vu_meter,
                self.model_selector,
                self.audio_mode_menu,
                ft.Container(expand=True),
                self.status_label,
                ft.Container(width=10),
                self.btn_area,
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(height=20),
                self.editor,
                ft.Divider(height=20),
                actions,
            ],
            expand=True,
        )

        self.content = ft.Row(controls=[self.sidebar, main_column], expand=True)

    # ==================================================================
    # Recording Flow (Async)
    # ==================================================================

    def _toggle_recording(self, e):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        self._is_recording = True
        self.record_btn.content.value = i18n.get("transcribe")
        self.record_btn.bgcolor = ft.Colors.GREEN_700
        self.cancel_btn.visible = True
        self.status_label.value = i18n.get("recording")
        self.status_label.color = ft.Colors.GREEN

        self.audio_mode_menu.disabled = True
        self.model_selector.disabled = True
        self.upload_btn.disabled = True
        self.update()

        self._record_start_time = time.time()
        self._timer_running = True
        self._start_timer_loop()

        mode = getattr(self.record_btn, "custom_mode", "mic")
        self._recorder.start_recording(mode=mode)

    def _start_timer_loop(self):
        """Timer loop usando threading.Timer (compatível com thread de áudio)."""
        if not self._timer_running:
            return
        elapsed = int(time.time() - self._record_start_time)
        mins, secs = divmod(elapsed, 60)
        self.timer_label.value = f"{mins:02d}:{secs:02d}"
        try:
            self.timer_label.update()
        except Exception:
            pass
        if self._timer_running:
            threading.Timer(0.5, self._start_timer_loop).start()

    def _cancel_recording(self, e):
        self._is_recording = False
        self._timer_running = False
        self._current_request_id += 1  # Invalida qualquer task ativa
        self.cancel_btn.visible = False

        # Cancela a task async se existir
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            self._active_task = None

        try:
            wav_path = self._recorder.stop_recording()
            import pathlib
            pathlib.Path(wav_path).unlink(missing_ok=True)
        except Exception:
            pass

        self._reset_recording_ui()
        self.status_label.value = i18n.get("context_reset")

    def _stop_recording(self) -> None:
        self._is_recording = False
        self._timer_running = False
        self.record_btn.disabled = True
        self.record_btn.content.value = i18n.get("processing")
        self.record_btn.bgcolor = ft.Colors.ORANGE_700
        self.status_label.value = i18n.get("transcribing")
        self.status_label.color = ft.Colors.ORANGE
        self.update()

        wav_path = self._current_audio_path
        self._current_audio_path = None

        if not wav_path:
            try:
                wav_path = self._recorder.stop_recording()
                print(f"[FLET DEBUG] Audio gravado em: {wav_path}")
            except Exception as exc:
                print(f"Erro no audio: {exc}")
                self._reset_recording_ui()
                return

        # Captura o request_id e a aba alvo ANTES de iniciar a task
        request_id = self._current_request_id
        audio_mode = getattr(self.record_btn, "custom_mode", "mic")

        # Dispara a transcrição como uma task async
        self._active_task = self.page.run_task(
            self._transcribe_async,
            Path(wav_path) if isinstance(wav_path, str) else wav_path,
            request_id,
            audio_mode,
        )

    async def _transcribe_async(
        self,
        wav_path: Path,
        request_id: int,
        audio_mode: str,
    ) -> None:
        """Task assíncrona: upload → agente stream → UI throttled."""
        from app.agents.transcriber_agent import (
            create_transcription_agent,
            upload_audio_async,
            delete_uploaded_file,
            transcribe_stream,
        )

        # Verifica se o request_id ainda é válido
        if request_id != self._current_request_id:
            return

        # Coleta prompt e keywords
        prompt_data = self.sidebar.get_active_prompt()
        prompt_text = prompt_data["texto_prompt"] if prompt_data else ""
        keywords = prompt_data["palavras_chave"] if prompt_data else []

        if audio_mode == "system":
            diarization_instruction = (
                "\n\n[Instrução Automática do Sistema]: O áudio a seguir contém múltiplos interlocutores. "
                "Por favor, deduzindo pelo contexto das frases e trocas de turno, separe as falas "
                "identificando-as explicitamente como 'Pessoa 1:', 'Pessoa 2:', etc."
            )
            prompt_text += diarization_instruction

        uploaded_file = None
        try:
            # 1. Upload assíncrono do áudio
            self.status_label.value = "Enviando áudio..."
            self.status_label.color = ft.Colors.ORANGE
            try:
                self.status_label.update()
            except Exception:
                pass

            uploaded_file = await upload_audio_async(wav_path)
            print(f"[FLET DEBUG] Upload concluído: {uploaded_file.name}")

            if request_id != self._current_request_id:
                return

            # 2. Cria o agente
            agent = create_transcription_agent(prompt_text, keywords)

            # 3. Stream assíncrono do agente
            self.status_label.value = i18n.get("transcribing")
            try:
                self.status_label.update()
            except Exception:
                pass

            active_tab = self.editor.active_tab
            if active_tab is None:
                return

            has_content = False
            async for chunk_text in transcribe_stream(agent, uploaded_file):
                if request_id != self._current_request_id:
                    return  # Cancelado pelo usuário

                has_content = True
                active_tab.insert_text(chunk_text)

                # Throttled update — só envia pro frontend a cada 100ms
                if active_tab.flush_update():
                    try:
                        self.page.update()
                    except Exception:
                        pass

            # 4. Force final update para garantir que todo texto apareceu
            if has_content:
                active_tab.force_update()
                try:
                    self.page.update()
                except Exception:
                    pass

            if not has_content:
                active_tab.insert_text("(Nenhuma fala detectada no áudio)")
                active_tab.force_update()

            # Sucesso
            self.status_label.value = "Transcrição concluída ✓"
            self.status_label.color = ft.Colors.GREEN

        except asyncio.CancelledError:
            print("[FLET DEBUG] Transcrição cancelada pelo usuário")
            self.status_label.value = i18n.get("context_reset")
            self.status_label.color = "#9ca3af"

        except Exception as exc:
            print(f"[FLET ERROR] Erro na transcrição: {type(exc).__name__}: {exc}")
            self.status_label.value = f"Erro: {exc}"
            self.status_label.color = ft.Colors.RED

        finally:
            # Cleanup: remove uploaded file e WAV local
            if uploaded_file:
                await delete_uploaded_file(uploaded_file)

            try:
                await asyncio.to_thread(wav_path.unlink, missing_ok=True)
            except Exception:
                pass

            self._reset_recording_ui()

    # ==================================================================
    # UI Helpers
    # ==================================================================

    def _reset_recording_ui(self) -> None:
        self.record_btn.disabled = False
        self.record_btn.content.value = i18n.get("record")
        mode = getattr(self.record_btn, "custom_mode", "mic")
        self.record_btn.bgcolor = "#b91c1c" if mode == "system" else ft.Colors.RED_700
        self.cancel_btn.visible = False
        self.status_label.value = i18n.get("ready")
        self.status_label.color = "#9ca3af"

        self.audio_mode_menu.disabled = False
        self.model_selector.disabled = False
        self.upload_btn.disabled = False
        self.vu_meter.reset()
        self.timer_label.value = "00:00"

        try:
            self.page.update()
        except Exception:
            pass

    def _on_language_change(self, e: ft.ControlEvent) -> None:
        """Altera o idioma globalmente e atualiza cada rótulo dinamicamente."""
        lang = e.control.selected[0]
        i18n.set_language(lang)

        self.app_title_text.value = i18n.get("app_title")
        self.online_status.value = i18n.get("online")
        self.history_btn.text = i18n.get("history")
        self.status_label.value = i18n.get("ready")

        self.record_btn.content.value = i18n.get("record")
        self.upload_btn.tooltip = i18n.get("upload")
        self.cancel_btn.content.value = i18n.get("cancel")
        self.copy_btn.content.value = i18n.get("copy")
        self.reset_btn.content.value = i18n.get("clear")

        try:
            self.page.update()
        except Exception:
            pass


def init_app(page: ft.Page):
    page.title = "Transcribe Assistant (Flet V2 — Agno)"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    app_view = FletApp(page)
    page.add(app_view)
    page.update()
