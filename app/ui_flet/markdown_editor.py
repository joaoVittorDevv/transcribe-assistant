"""Área principal de edição e visualização de texto no Flet."""

import flet as ft

class MarkdownEditor(ft.Container):
    def __init__(self):
        super().__init__()
        self.expand = True
        
        self.textfield = ft.TextField(
            multiline=True,
            expand=True,
            text_size=16,
            border=ft.InputBorder.NONE,
            bgcolor=ft.Colors.TRANSPARENT,
            hint_text="Sua transcrição aparecerá aqui..."
        )
        
        self.content = ft.Container(
            content=self.textfield,
            expand=True,
            bgcolor="#111827",
            padding=10,
            border_radius=8,
            border=ft.border.all(1, "#374151")
        )
        
    def insert_text(self, new_text: str):
        """No Flet TextField atualizamos o valor completo. O cursor e scroll tendem a manter posição final."""
        current = self.textfield.value or ""
        # Adiciona espaco se não for vazio e o texto não começar com espaço (logica parecida com Tkinter)
        prefix = " " if current and not new_text.startswith(" ") else ""
        self.textfield.value = current + prefix + new_text
        
        try:
            self.textfield.update()
        except Exception:
            pass
            
    def get_text(self) -> str:
        return self.textfield.value or ""
