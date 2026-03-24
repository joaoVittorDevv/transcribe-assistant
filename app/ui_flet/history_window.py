"""app.ui_flet.history_window — Modal de Histórico de Sessões em Flet."""

import flet as ft
import i18n
import app.database as db

class HistoryModal:
    def __init__(self, page: ft.Page, on_restore=None):
        self.page = page
        self.on_restore = on_restore
        
        self.list_view = ft.ListView(expand=True, spacing=10)
        self.dialog = ft.AlertDialog(
            title=ft.Text(i18n.t("ui.history.title", default="Histórico das Transcrições"), size=20, weight="bold"),
            content=ft.Container(self.list_view, width=650, height=450),
            actions=[ft.TextButton("Fechar", on_click=self.close)]
        )

    def show(self):
        self._load_sessions()
        if hasattr(self.page, "open"):
            self.page.open(self.dialog)
        else:
            self.page.dialog = self.dialog
            self.dialog.open = True
            self.page.update()

    def close(self, e=None):
        if hasattr(self.page, "close"):
            self.page.close(self.dialog)
        else:
            self.dialog.open = False
            self.page.update()

    def _load_sessions(self):
        self.list_view.controls.clear()
        sessions = db.get_all_sessions()
        
        if not sessions:
            self.list_view.controls.append(
                ft.Text(i18n.t("ui.history.no_sessions", default="Nenhuma sessão no histórico."), color="gray")
            )
        else:
            for session in sessions:
                try:
                    qty = session["quantidade_interacoes"]
                except IndexError:
                    qty = 1
                    
                preview = session["conteudo_texto"][:220].replace("\n", " ")
                if len(session["conteudo_texto"]) > 220:
                    preview += "..."
                    
                card = ft.Card(
                    elevation=3,
                    content=ft.Container(
                        padding=15,
                        content=ft.Column([
                            ft.Row([
                                ft.Text(f"📅 {session['atualizado_em']}", size=12, color="gray"),
                                ft.Text(f"Interações: {qty}", size=12, color="gray")
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(preview, size=14),
                            ft.Row([
                                ft.OutlinedButton(
                                    i18n.t("ui.buttons.copy", default="Copiar"),
                                    icon=ft.Icons.COPY,
                                    on_click=lambda e, txt=session["conteudo_texto"]: self._copy(txt)
                                ),
                                ft.ElevatedButton(
                                    i18n.t("ui.buttons.restore", default="Restaurar"),
                                    icon=ft.Icons.RESTORE,
                                    bgcolor="#2563eb",
                                    color="white",
                                    on_click=lambda e, sess=session: self._restore(sess)
                                )
                            ], alignment=ft.MainAxisAlignment.END)
                        ])
                    )
                )
                self.list_view.controls.append(card)

    def _copy(self, text):
        self.page.run_task(ft.Clipboard().set, text)
        
    def _restore(self, session):
        if self.on_restore:
            self.on_restore(session["id"], session["conteudo_texto"])
        self.close()
