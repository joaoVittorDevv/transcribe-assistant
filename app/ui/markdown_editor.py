"""
CustomTkinter Markdown Editor UI component.
Wraps a CTkTextbox and adds a format toolbar above it, converting the text in the text area manually.
Intercepts Ctrl+C for HTML/Rich Text clipboard output.
"""

from __future__ import annotations

import tkinter
import markdown
import customtkinter as ctk

from app.utils.clipboard_manager import copy_html_to_clipboard

# CSS styles applied to the converted HTML to look acceptable in Word/Google Docs
_HTML_STYLE = """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; font-size: 11pt; line-height: 1.5; }
code { font-family: Consolas, "Courier New", monospace; background-color: #f3f4f6; padding: 2px 4px; border-radius: 4px; font-size: 10pt; }
pre { background-color: #f3f4f6; padding: 12px; border-radius: 6px; border: 1px solid #e5e7eb; overflow-x: auto; }
pre code { background-color: transparent; padding: 0; }
h1, h2, h3, h4 { font-family: inherit; margin-top: 1em; margin-bottom: 0.5em; font-weight: 600; }
</style>
"""


class MarkdownEditor(ctk.CTkFrame):
    """
    Componente customizado contendo a UI da Toolbar e o Textbox nativo do CTk.
    """

    def __init__(
        self, master, fg_color="transparent", bg_color="transparent", **kwargs
    ):
        super().__init__(master, fg_color=fg_color, bg_color=bg_color, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()

        self._textbox = ctk.CTkTextbox(
            self,
            font=("", 14),
            wrap="word",
            state="normal",
        )
        self._textbox.grid(row=1, column=0, sticky="nsew", pady=0)

        # Tratar atalhos globais específicos para a caixa de texto
        self._textbox.bind("<Control-c>", self._on_smart_copy)
        # MacOS Support
        self._textbox.bind("<Command-c>", self._on_smart_copy)

        # Debaunce text typing binding variables
        self._key_release_bind_id = None
        self._custom_change_callback = None

    def _build_toolbar(self) -> None:
        """Contrói uma barra superior com os botões de formatação."""
        self._toolbar_frame = ctk.CTkFrame(
            self, fg_color=("gray90", "gray15"), corner_radius=6, height=36
        )
        self._toolbar_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        # Botões da Toolbar
        # Botão Bold
        self._btn_bold = self._create_toolbar_button(
            self._toolbar_frame,
            "B",
            font=("", 14, "bold"),
            command=lambda: self._apply_format("**"),
        )
        self._btn_bold.pack(side="left", padx=(4, 2), pady=4)

        # Botão Italic
        self._btn_italic = self._create_toolbar_button(
            self._toolbar_frame,
            "I",
            font=("", 14, "italic"),
            command=lambda: self._apply_format("*"),
        )
        self._btn_italic.pack(side="left", padx=2, pady=4)

        # Separador visual
        ctk.CTkLabel(self._toolbar_frame, text="|", text_color="gray50").pack(
            side="left", padx=2, pady=4
        )

        # Code Block
        self._btn_code = self._create_toolbar_button(
            self._toolbar_frame,
            "</>",
            command=lambda: self._apply_format("```\n", suffix="\n```"),
        )
        self._btn_code.pack(side="left", padx=2, pady=4)

        # Inline Code
        self._btn_inline_code = self._create_toolbar_button(
            self._toolbar_frame, "`", command=lambda: self._apply_format("`")
        )
        self._btn_inline_code.pack(side="left", padx=2, pady=4)

        # Separador visual
        ctk.CTkLabel(self._toolbar_frame, text="|", text_color="gray50").pack(
            side="left", padx=2, pady=4
        )

        # Headers
        self._btn_h1 = self._create_toolbar_button(
            self._toolbar_frame,
            "H1",
            font=("", 13, "bold"),
            command=lambda: self._apply_format("# ", prefix_only=True),
        )
        self._btn_h1.pack(side="left", padx=2, pady=4)

        self._btn_h2 = self._create_toolbar_button(
            self._toolbar_frame,
            "H2",
            font=("", 12, "bold"),
            command=lambda: self._apply_format("## ", prefix_only=True),
        )
        self._btn_h2.pack(side="left", padx=2, pady=4)

        self._btn_h3 = self._create_toolbar_button(
            self._toolbar_frame,
            "H3",
            font=("", 11, "bold"),
            command=lambda: self._apply_format("### ", prefix_only=True),
        )
        self._btn_h3.pack(side="left", padx=2, pady=4)

    def _create_toolbar_button(
        self, parent, text, font=("", 14), command=None
    ) -> ctk.CTkButton:
        """A helper to build uniform format buttons."""
        return ctk.CTkButton(
            parent,
            text=text,
            width=30,
            height=28,
            font=font,
            corner_radius=4,
            fg_color="transparent",
            hover_color=("gray85", "gray30"),
            text_color=("gray10", "gray90"),
            command=command,
        )

    def _apply_format(
        self, wrap_str: str, suffix: str | None = None, prefix_only: bool = False
    ) -> None:
        """Injeta a sintaxe Markdown na seleção atual ou onde o cursor está."""
        try:
            # Pegar posição da seleção SE houver
            idx_start = self._textbox.index("sel.first")
            idx_end = self._textbox.index("sel.last")
            selected_text = self._textbox.get(idx_start, idx_end)
            has_selection = True
        except tkinter.TclError:
            # Sem texto selecionado, pegamos a posição atual do insert
            idx_start = self._textbox.index("insert")
            idx_end = idx_start
            selected_text = ""
            has_selection = False

        if not suffix:
            suffix = wrap_str

        # Aplicar
        self._textbox.delete(idx_start, idx_end)

        if prefix_only:
            # Apenas colocar algo no início da linha, útil para Headers
            line_str = idx_start.split(".")[0]
            col_str = idx_start.split(".")[1]

            # Precisamos injetar o prefixo no início da linha ou na seleção atual
            # Por simplicidade da implementação de header, injetamos '# ' no inicio ou antes da seleção
            # Vamos buscar manter a injecção direta:
            final_text = f"{wrap_str}{selected_text}"
            self._textbox.insert(idx_start, final_text)

            new_cursor_idx = f"{line_str}.{int(col_str) + len(final_text)}"

        else:
            final_text = f"{wrap_str}{selected_text}{suffix}"
            self._textbox.insert(idx_start, final_text)

            # Reposicionar o cursor
            line_str = idx_start.split(".")[0]
            col_str = int(idx_start.split(".")[1])
            if has_selection:
                new_cursor_idx = f"{line_str}.{col_str + len(final_text)}"
            else:
                new_cursor_idx = f"{line_str}.{col_str + len(wrap_str)}"

        self._textbox.mark_set("insert", new_cursor_idx)
        self._textbox.focus_set()

        # Trigger o evento de onChange manual
        if self._custom_change_callback:
            self._custom_change_callback()

    # ==========================================================
    # Integração externa e Eventos
    # ==========================================================

    def bind_text_change(self, callback) -> None:
        """Allow parent container to bind directly to textbox changes"""
        self._custom_change_callback = callback

        def _on_key(event):
            callback(event)

        self._textbox.bind("<KeyRelease>", _on_key)

    def get_text(self) -> str:
        """Puxar texto todo da caixa."""
        return self._textbox.get("1.0", "end").strip()

    def insert_text(self, text: str, index="insert", see=True) -> None:
        """Inserir texto numa posição, parecido com o CTkTextbox tradicional."""
        self._textbox.insert(index, text)
        if see:
            self._textbox.see(index)

    def delete_text(self, start="1.0", end="end") -> None:
        """Esvaziar caixa de texto."""
        self._textbox.delete(start, end)

    # ==========================================================
    # O SMART COPY LOGIC
    # ==========================================================
    def _on_smart_copy(self, event=None) -> str:
        """
        Intercepta o Ctr+C para colocar Markdown nativamente no Clipboard Tkinter (Texto Plano)
        mas enviar os dados Ocultos em HTML pro clipboard de RichText do OS.
        """
        try:
            # Tentar pegar texto selecionado
            text_to_copy = self._textbox.get("sel.first", "sel.last")
        except tkinter.TclError:
            # Nada selecionado, copia tudo? O Tkinter original não avisa, mas vamos copiar tudo
            text_to_copy = self.get_text()

        if not text_to_copy:
            return "break"  # Ignorar copy se vazio

        # Limpar clipboard antigo e jogar o Texto raw pro Tkinter/sistema base
        self.clipboard_clear()
        self.clipboard_append(text_to_copy)

        # Converter texto selecionado pro Markdown (HTML limpo) usando Extensões essenciais
        try:
            html_body = markdown.markdown(
                text_to_copy, extensions=["fenced_code", "tables"]
            )
            html_final = (
                f"<html><head>{_HTML_STYLE}</head><body>{html_body}</body></html>"
            )

            # Ping utilitário para forçar xclip na porta text/html
            copy_html_to_clipboard(html_final)
            print("[DEBUG] Ctrl+C Interceptado e injectado as MIME/HTML Rich text")
        except Exception as e:
            print(f"[DEBUG] Erro a tentar gerar HTML copy: {e}")

        # Retornar "break" impede o event loop do Tkinter de processar duas cópias ao mesmo tempo
        return "break"
