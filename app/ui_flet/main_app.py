import flet as ft
from app.audio_recorder import AudioRecorder
from app.transcriber import Transcriber
from app.network_monitor import NetworkMonitor
from app.ui_flet.sidebar import Sidebar
from app.ui_flet.markdown_editor import MarkdownEditor
import time
import threading

class FletApp(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.expand = True
        
        # --- Serviços (Backend Igual ao Tkinter) ---
        self._network_monitor = NetworkMonitor(on_status_change=self._on_network_change)
        self._recorder = AudioRecorder(on_rms_update=self._on_rms)
        self._transcriber = Transcriber(is_online_fn=lambda: self._network_monitor.is_online)
        self._network_monitor.start()
        
        self._is_recording = False
        
        self._build_ui()
        
    def _on_network_change(self, status):
        pass # To do: update network indicator visual
        
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
        text = self.editor.get_text()
        if text:
            self.page.run_task(ft.Clipboard().set, text)
            self.status_label.value = "Texto copiado!"
            self.status_label.color = ft.Colors.GREEN
            try:
                self.status_label.update()
            except Exception:
                pass

    def _on_history_restore(self, session_id, texto):
        self.editor.textfield.value = texto
        try:
            self.editor.textfield.update()
        except Exception:
            pass

    def _clear_text(self, e):
        self.editor.textfield.value = ""
        try:
            self.editor.textfield.update()
        except Exception:
            pass

    def _build_ui(self):
        # Componentes Filhos
        self.sidebar = Sidebar()
        self.editor = MarkdownEditor()
        
        # Header Top Bar
        from app.ui_flet.history_window import HistoryModal
        
        self.history_btn = ft.ElevatedButton(
            "Histórico",
            icon=ft.Icons.HISTORY,
            bgcolor="#4b5563",
            color="white",
            on_click=lambda e: HistoryModal(self.page, on_restore=self._on_history_restore).show()
        )
        
        header = ft.Row(
            controls=[
                ft.Icon(ft.Icons.MIC, size=32, color=ft.Colors.BLUE_400),
                ft.Text("Assistente de Transcrição", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                self.history_btn,
                ft.Text("Online ⚡", color=ft.Colors.GREEN) # Mock
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        # ----- Controles Inferiores (Esquerda: Timer, VUMeter, Modos. Direita: Gravar, Copiar) -----
        self.timer_label = ft.Text("00:00", size=24, weight=ft.FontWeight.BOLD)
        from app.ui_flet.vu_meter import VUMeter
        self.vu_meter = VUMeter(width=30, height=45)
        
        # Seletor de Modelo
        self.model_selector = ft.Dropdown(
            options=[
                ft.dropdown.Option("Auto"),
                ft.dropdown.Option("Google Gemini"),
                ft.dropdown.Option("Whisper")
            ],
            value="Auto",
            width=140,
            text_size=12,
            height=45
        )
        
        # Seletor Microfone x Sistema
        self.audio_mode_menu = ft.Dropdown(
            options=[
                ft.dropdown.Option("mic", text="🎙️"),
                ft.dropdown.Option("system", text="🎧")
            ],
            value="mic",
            width=60,
            text_size=16,
            height=45,
            on_select=self._on_audio_mode_change
        )
        
        # Area de botões dinâmicos
        self.btn_area = ft.Row(spacing=5)
        
        self.record_btn = ft.Button(
            content=ft.Text("Gravar", weight=ft.FontWeight.BOLD),
            icon=ft.Icons.MIC_NONE,
            on_click=self._toggle_recording,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE,
            height=45
        )
        self.record_btn.custom_mode = "mic"
        
        self.cancel_btn = ft.Button(
            content=ft.Text("Cancelar"),
            on_click=self._cancel_recording,
            bgcolor="#4b5563",
            color=ft.Colors.WHITE,
            height=45,
            visible=False
        )
        
        self.copy_btn = ft.Button(
            content=ft.Text("Copiar"),
            icon=ft.Icons.COPY,
            on_click=self._copy_text,
            height=45
        )
        
        self.reset_btn = ft.Button(
            content=ft.Text("Limpar"),
            icon=ft.Icons.DELETE_OUTLINE,
            on_click=self._clear_text,
            height=45
        )
        
        self.btn_area.controls = [self.record_btn, self.cancel_btn, self.copy_btn, self.reset_btn]
        
        self.status_label = ft.Text("Pronto.", color="#9ca3af", size=12)
        
        actions = ft.Row(
            controls=[
                self.timer_label,
                self.vu_meter,
                self.model_selector,
                self.audio_mode_menu,
                ft.Container(expand=True),  # Espaçador Flexível central
                self.status_label,
                ft.Container(width=10),
                self.btn_area
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        main_column = ft.Column(
            controls=[
                header,
                ft.Divider(height=20),
                self.editor,
                ft.Divider(height=20),
                actions
            ],
            expand=True
        )
        
        self.content = ft.Row(
            controls=[
                self.sidebar,
                main_column
            ],
            expand=True
        )

    # --- Lógica Conectada ---
    
    def _toggle_recording(self, e):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()
            
    def _start_recording(self):
        self._is_recording = True
        self.record_btn.content.value = "Transcrever"
        self.record_btn.bgcolor = ft.Colors.GREEN_700
        self.cancel_btn.visible = True
        self.status_label.value = "Gravando..."
        self.status_label.color = ft.Colors.GREEN
        
        self.audio_mode_menu.disabled = True
        self.model_selector.disabled = True
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
        self.status_label.value = "Contexto resetado."
        
    def _stop_recording(self):
        self._is_recording = False
        self.record_btn.disabled = True
        self.record_btn.content.value = "Processando..."
        self.record_btn.bgcolor = ft.Colors.ORANGE_700
        self.status_label.value = "Transcrevendo áudio..."
        self.status_label.color = ft.Colors.ORANGE
        self.update()
        
        # Para a gravação do audio fisicamente
        try:
            wav_path = self._recorder.stop_recording()
            print(f"[FLET DEBUG] Audio salvo em: {wav_path}")
        except Exception as exc:
            print(f"Erro no audio: {exc}")
            self._reset_recording_ui()
            return
            
        # Roda a transcrição em thread separada como no Original
        threading.Thread(
            target=self._transcribe_worker,
            args=(wav_path,),
            daemon=True
        ).start()

    def _transcribe_worker(self, wav_path):
        prompt_data = self.sidebar.get_active_prompt()
        prompt_text = prompt_data["texto_prompt"] if prompt_data else ""
        keywords = prompt_data["palavras_chave"] if prompt_data else []
        
        try:
            # Assincronamente escreve os chunks na interface
            def handle_chunk(chunk_text: str):
                self.editor.insert_text(chunk_text)
                
            text = self._transcriber.transcribe(
                wav_path, 
                prompt_text, 
                keywords, 
                "auto", 
                on_chunk=handle_chunk
            )
            
            # Se não teve stream, adiciona o total
            if not getattr(self._transcriber, '_last_was_stream', False) and text:
                self.editor.insert_text(text)
                
        except Exception as e:
            print(f"[Erro na Transcrição] {e}")
        finally:
            self._reset_recording_ui()

    def _reset_recording_ui(self):
        self.record_btn.disabled = False
        self.record_btn.content.value = "Gravar"
        mode = getattr(self.record_btn, "custom_mode", "mic")
        self.record_btn.bgcolor = "#b91c1c" if mode == "system" else ft.Colors.RED_700
        self.cancel_btn.visible = False
        self.status_label.value = "Pronto."
        self.status_label.color = "#9ca3af"
        
        self.audio_mode_menu.disabled = False
        self.model_selector.disabled = False
        self.vu_meter.set_level(0.0)
        self.timer_label.value = "00:00"
        
        # Update da interface usando page para lidar com contexto thread-safe
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
