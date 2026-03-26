import flet as ft
from app.audio_recorder import AudioRecorder
from app.transcriber import Transcriber
from app.network_monitor import NetworkMonitor
from app.ui_flet.sidebar import Sidebar
from app.ui_flet.tab_manager import TabManager
from app.utils.i18n_manager import i18n
from app.ui.native_dialog import open_audio_file
from app.audio_validator import SUPPORTED_AUDIO_EXTENSIONS
import time
import threading
import os


class FletApp(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.expand = True
        self._page = page  # Armazenado para uso nos componentes filhos

        # --- Serviços (Backend Igual ao Tkinter) ---
        self._network_monitor = NetworkMonitor(on_status_change=self._on_network_change)
        self._recorder = AudioRecorder(on_rms_update=self._on_rms)
        self._transcriber = Transcriber(
            is_online_fn=lambda: self._network_monitor.is_online
        )
        self._network_monitor.start()

        self._is_recording = False
        self._current_audio_path: str | None = None

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
            self.page.run_task(ft.Clipboard().set, text)
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
        """Abre o seletor nativo de arquivos de áudio (Zenity/Tkinter).
        Utiliza a mesma lógica do projeto original para garantir compatibilidade.
        """
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
        self.editor.add_tab()  # Abre a primeira aba por padrão

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

        # Botão Upload (Clips) - Movido para o Topo
        self.upload_btn = ft.IconButton(
            icon=ft.Icons.ATTACH_FILE_ROUNDED,
            icon_color=ft.Colors.GREY_400,
            tooltip=i18n.get("upload"),
            on_click=self._open_file_picker,
        )

        header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.MIC, size=32, color=ft.Colors.BLUE_400),
                self.app_title_text,
                ft.Container(expand=True),
                self.lang_toggle,
                self.upload_btn,  # Posicionado aqui
                ft.VerticalDivider(width=10),
                self.history_btn,
                self.online_status,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # ----- Controles Inferiores (Esquerda: Timer, VUMeter, Modos. Direita: Gravar, Copiar) -----
        self.timer_label = ft.Text("00:00", size=24, weight=ft.FontWeight.BOLD)
        from app.ui_flet.vu_meter import VuMeter

        self.vu_meter = VuMeter(num_leds=20, led_width=7, led_height=18, spacing=2)

        # Seletor de Modelo
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

        # Seletor Microfone x Sistema
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

        # Area de botões dinâmicos
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
                ft.Container(expand=True),  # Espaçador Flexível central
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

    # --- Lógica Conectada ---

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
        self._update_timer()

        mode = getattr(self.record_btn, "custom_mode", "mic")
        self._recorder.start_recording(mode=mode)

    def _update_timer(self):
        if not self._is_recording:
            return
        elapsed = int(time.time() - self._record_start_time)
        mins, secs = divmod(elapsed, 60)
        self.timer_label.value = f"{mins:02d}:{secs:02d}"
        try:
            self.timer_label.update()
            # Flet nao tem loop de after interno nativo como tk, usa async sleep em background
            # Porem, criar thread para rodar loop:
            threading.Timer(0.5, self._update_timer).start()
        except Exception:
            pass

    def _cancel_recording(self, e):
        self._is_recording = False
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
        self.record_btn.disabled = True
        self.record_btn.content.value = i18n.get("processing")
        self.record_btn.bgcolor = ft.Colors.ORANGE_700
        self.status_label.value = i18n.get("transcribing")
        self.status_label.color = ft.Colors.ORANGE
        self.update()

        # Decide se transcreve o arquivo selecionado ou o audio gravado
        wav_path = self._current_audio_path
        self._current_audio_path = None

        if not wav_path:
            # Para a gravação do audio fisicamente se for modo gravador
            try:
                wav_path = self._recorder.stop_recording()
                print(f"[FLET DEBUG] Audio gravado em: {wav_path}")
            except Exception as exc:
                print(f"Erro no audio: {exc}")
                self._reset_recording_ui()
                return

        # Roda a transcrição em thread separada como no Original
        threading.Thread(
            target=self._transcribe_worker, args=(wav_path,), daemon=True
        ).start()

    def _transcribe_worker(self, wav_path):
        prompt_data = self.sidebar.get_active_prompt()
        prompt_text = prompt_data["texto_prompt"] if prompt_data else ""
        keywords = prompt_data["palavras_chave"] if prompt_data else []

        try:
            # Assincronamente escreve os chunks na interface
            def handle_chunk(chunk_text: str) -> None:
                self.editor.insert_text_active(chunk_text)
                try:
                    self.page.update()
                except Exception:
                    pass

            text = self._transcriber.transcribe(
                wav_path, prompt_text, keywords, "auto", on_chunk=handle_chunk
            )

            # Se não teve stream, adiciona o total
            if not getattr(self._transcriber, "_last_was_stream", False) and text:
                self.editor.insert_text_active(text)

        except Exception as e:
            print(f"[Erro na Transcrição] {e}")
        finally:
            self._reset_recording_ui()

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

        # Update da interface usando page para lidar com contexto thread-safe
        try:
            self.page.update()
        except Exception:
            pass

    def _on_language_change(self, e: ft.ControlEvent) -> None:
        """Altera o idioma globalmente e atualiza cada rótulo dinamicamente."""
        lang = e.control.selected[0]
        i18n.set_language(lang)

        # Atualização dinâmica de labels persistentes mapeados
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
    page.title = "Transcribe Assistant (Flet V1)"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20

    app_view = FletApp(page)
    page.add(app_view)
    page.update()
