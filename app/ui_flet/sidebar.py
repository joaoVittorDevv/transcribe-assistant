"""Menu lateral em Flet para seleção de prompts."""

import flet as ft
import i18n
import app.database as db

class Sidebar(ft.Container):
    def __init__(self, on_prompt_changed=None):
        super().__init__()
        self.on_prompt_changed = on_prompt_changed
        self.width = 240
        self.bgcolor = ft.Colors.SURFACE
        self.padding = 15
        self.border_radius = 8
        self.margin = ft.margin.only(right=10)
        
        self.selected_prompt_id = None
        self.prompts = []
        
        self._build_ui()
        self.refresh_prompts()

    def _build_ui(self):
        # Título
        self.title_label = ft.Text(i18n.t("ui.sidebar.title", default="Modelos de Prompt"), size=16, weight=ft.FontWeight.BOLD)
        
        # Grupo de Radio Buttons para os prompts com scroll
        self.radio_group = ft.RadioGroup(
            content=ft.Column(scroll=ft.ScrollMode.AUTO),
            on_change=self._on_radio_change
        )
        
        # Botão Gerenciar Prompts
        self.manage_btn = ft.OutlinedButton(
            content=ft.Text(i18n.t("ui.sidebar.manage_prompts", default="Gerenciar Prompts")),
            icon=ft.Icons.SETTINGS,
            on_click=self._on_manage_click
        )

        self.content = ft.Column(
            controls=[
                self.title_label,
                ft.Divider(height=1),
                ft.Container(content=self.radio_group, expand=True),
                self.manage_btn
            ],
            expand=True
        )

    def refresh_prompts(self):
        self.prompts = db.get_all_prompts()
        self.radio_group.content.controls.clear()
        
        if not self.prompts:
            self.radio_group.content.controls.append(
                ft.Text(i18n.t("ui.sidebar.no_prompts", default="Nenhum prompt"), color="#9ca3af")
            )
            self.selected_prompt_id = None
        else:
            for p in self.prompts:
                label = p["nome"]
                try:
                    is_default = p["is_default"]
                except IndexError:
                    is_default = 0
                if is_default:
                    label += " (Padrão)"
                    if self.selected_prompt_id is None:
                        self.selected_prompt_id = str(p["id"])
                
                self.radio_group.content.controls.append(
                    ft.Radio(value=str(p["id"]), label=label)
                )

            if self.selected_prompt_id:
                self.radio_group.value = self.selected_prompt_id

        # Verifica se o controle já está na página antes de chamar update()
        try:
            self.update()
        except Exception:
            pass

    def _on_radio_change(self, e):
        self.selected_prompt_id = e.control.value
        if self.on_prompt_changed:
            self.on_prompt_changed()

    def _on_manage_click(self, e):
        from app.ui_flet.prompt_modal import PromptModal
        if self.page:
            modal = PromptModal(self.page, on_changed=self.refresh_prompts)
            modal.show()
        
    def get_active_prompt(self) -> dict | None:
        if not self.selected_prompt_id:
            return None
        
        try:
            pid = int(self.selected_prompt_id)
        except ValueError:
            return None
            
        prompt = db.get_prompt_by_id(pid)
        if not prompt:
            return None
            
        keywords = db.get_keywords_by_prompt(pid)
        return {
            "id": prompt["id"],
            "nome": prompt["nome"],
            "texto_prompt": prompt["texto_prompt"],
            "palavras_chave": [row["palavra"] for row in keywords],
        }
