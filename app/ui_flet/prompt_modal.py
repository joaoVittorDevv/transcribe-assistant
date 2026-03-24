"""app.ui_flet.prompt_modal — Modal de Gerenciamento de Prompts em Flet."""

import flet as ft
import i18n
import app.database as db

class PromptModal:
    def __init__(self, page: ft.Page, on_changed=None):
        self.page = page
        self.on_changed = on_changed
        self._selected_prompt_id = None
        self._keyword_vars = []
        
        self._build_dialog()

    def _build_dialog(self):
        # Componentes do Form
        self.name_input = ft.TextField(label=i18n.t("ui.prompts.name_label", default="Nome do Prompt"))
        self.text_input = ft.TextField(
            label=i18n.t("ui.prompts.text_label", default="Texto do Prompt"), 
            multiline=True, 
            min_lines=6,
            max_lines=6
        )
        self.kw_input = ft.TextField(
            label=i18n.t("ui.prompts.add_keyword_placeholder", default="Nova palavra-chave"), 
            expand=True, 
            on_submit=self._add_keyword
        )
        self.kw_list = ft.Row(wrap=True, scroll=ft.ScrollMode.AUTO, height=100, run_spacing=5)
        self.is_default_switch = ft.Switch(label="Definir como Padrão")
        
        # Botoes Form
        self.save_btn = ft.ElevatedButton(
            i18n.t("ui.buttons.save", default="Salvar"), 
            icon=ft.Icons.SAVE,
            bgcolor="#15803d",
            color="white",
            on_click=self._on_save
        )
        self.delete_btn = ft.ElevatedButton(
            i18n.t("ui.buttons.delete", default="Excluir"), 
            icon=ft.Icons.DELETE,
            bgcolor="#b91c1c",
            color="white",
            disabled=True,
            on_click=self._on_delete
        )
        self.new_btn = ft.ElevatedButton(
            i18n.t("ui.prompts.new", default="+ Novo Prompt"), 
            on_click=lambda e: self._on_new()
        )
        
        # Lista Lateral
        self.prompts_list = ft.ListView(expand=True, spacing=5)
        
        left_panel = ft.Container(
            content=ft.Column([
                ft.Text(i18n.t("ui.prompts.list_title", default="Prompts"), size=16, weight="bold"),
                ft.Divider(),
                self.prompts_list,
                self.new_btn
            ]),
            width=220,
            border=ft.border.only(right=ft.border.BorderSide(1, "grey")),
            padding=ft.padding.only(right=15)
        )
        
        right_panel = ft.Container(
            content=ft.Column([
                self.name_input,
                self.text_input,
                ft.Row([self.kw_input, ft.IconButton(ft.Icons.ADD, on_click=self._add_keyword)]),
                ft.Container(content=self.kw_list, border=ft.border.all(1, "grey"), padding=5, border_radius=5),
                ft.Divider(height=10),
                self.is_default_switch,
                ft.Row([self.save_btn, self.delete_btn])
            ], scroll=ft.ScrollMode.AUTO),
            expand=True,
            padding=ft.padding.only(left=15)
        )
        
        self.dialog = ft.AlertDialog(
            title=ft.Text(i18n.t("ui.prompts.title", default="Gerenciador de Prompts"), size=20, weight="bold"),
            content=ft.Row([left_panel, right_panel], width=800, height=520, vertical_alignment=ft.CrossAxisAlignment.START),
            actions=[ft.TextButton("Fechar", on_click=self.close)]
        )

    def show(self):
        self._load_list()
        self._on_new()
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def close(self, e=None):
        self.dialog.open = False
        self.page.update()
        if self.dialog in self.page.overlay:
            self.page.overlay.remove(self.dialog)
            self.page.update()

    # --- CRUD Backend ---
    def _load_list(self):
        self.prompts_list.controls.clear()
        prompts = db.get_all_prompts()
        for p in prompts:
            btn = ft.TextButton(
                p["nome"], 
                on_click=lambda e, prompt=p: self._load_form(prompt),
                width=200
            )
            self.prompts_list.controls.append(btn)
        try:
            self.prompts_list.update()
        except:
            pass

    def _load_form(self, prompt):
        self._selected_prompt_id = prompt["id"]
        self.delete_btn.disabled = False
        
        self.name_input.value = prompt["nome"]
        self.text_input.value = prompt["texto_prompt"]
        
        try:
            is_def = prompt["is_default"]
        except IndexError:
            is_def = 0
            
        self.is_default_switch.value = bool(is_def)
        
        rows = db.get_keywords_by_prompt(prompt["id"])
        self._keyword_vars = [row["palavra"] for row in rows]
        
        self._render_keywords()
        self._safe_update_right()

    def _add_keyword(self, e):
        word = self.kw_input.value.strip() if self.kw_input.value else ""
        if word and word not in self._keyword_vars:
            self._keyword_vars.append(word)
            self.kw_input.value = ""
            self._render_keywords()

    def _remove_keyword(self, word):
        if word in self._keyword_vars:
            self._keyword_vars.remove(word)
            self._render_keywords()

    def _render_keywords(self):
        self.kw_list.controls.clear()
        for word in self._keyword_vars:
            chip = ft.Chip(
                label=ft.Text(word),
                on_delete=lambda e, w=word: self._remove_keyword(w)
            )
            self.kw_list.controls.append(chip)
        self._safe_update_right()

    def _on_new(self):
        self._selected_prompt_id = None
        self.delete_btn.disabled = True
        self.name_input.value = ""
        self.text_input.value = ""
        self.is_default_switch.value = False
        self._keyword_vars = []
        self._render_keywords()

    def _on_save(self, e):
        nome = self.name_input.value.strip() if self.name_input.value else ""
        texto = self.text_input.value.strip() if self.text_input.value else ""
        
        if not nome:
            # Em Flet mostramos um SnackBar para erro
            self.page.overlay.append(ft.SnackBar(ft.Text("Nome do prompt não pode ser vazio!"), open=True))
            self.page.update()
            return

        is_def = self.is_default_switch.value
        
        if is_def:
            current = db.get_default_prompt()
            # Flet blockable confirmation is tricky without callbacks, 
            # I will assume replacing default directly for MVP.
            pass

        if self._selected_prompt_id is None:
            pid = db.create_prompt(nome, texto, is_def)
            self._selected_prompt_id = pid
        else:
            pid = self._selected_prompt_id
            db.update_prompt(pid, nome, texto, is_def)

        db.replace_keywords(pid, self._keyword_vars)
        self.delete_btn.disabled = False
        
        self._load_list()
        self._safe_update_right()
        
        if self.on_changed:
            self.on_changed()

    def _on_delete(self, e):
        if self._selected_prompt_id is None:
            return
        db.delete_prompt(self._selected_prompt_id)
        self._on_new()
        self._load_list()
        
        if self.on_changed:
            self.on_changed()

    def _safe_update_right(self):
        try:
            self.name_input.update()
            self.text_input.update()
            self.kw_input.update()
            self.kw_list.update()
            self.is_default_switch.update()
            self.delete_btn.update()
        except:
            pass
