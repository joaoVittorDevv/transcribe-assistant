"""Componente de aba individual de transcrição com estado completamente isolado.

Cada instância de AbaTranscricao é autossuficiente: gerencia seu próprio
campo de texto, seu próprio título editável e suas próprias flags de estado.
Nenhum dado vaza entre instâncias.

Inclui suporte a formatação Markdown com:
- Barra de ferramentas com botões de formatação
- Preview em tempo real (split view)
"""

from __future__ import annotations

import flet as ft

from app.ui_flet.markdown import MarkdownPreview, MarkdownToolbar


class AbaTranscricao:
    """Encapsula uma aba individual de transcrição com estado completamente isolado.

    Cada instância gerencia:
    - ``_header_field``: Campo de título editável inline (injetado em ``ft.Tab.label``).
    - ``_body``: Campo de texto multilinhas com suporte a Markdown.
    - ``_toolbar``: Barra de ferramentas Markdown.
    - ``_preview``: Componente de preview renderizado.
    - Flags de controle: ``_title_edited_manually``, ``_first_insert`` e ``_preview_visible``.

    A classe *não* herda de ``ft.Control`` diretamente para evitar registro duplo
    no widget tree do Flet. Os controles são expostos por propriedades e injetados
    externamente pelo ``TabManager``.

    Layout (Split View):
    ┌─────────────────────────────────────────┐
    │ [Toolbar: B I S Code Link H1 H2 H3 ...] │
    ├───────────────────┬─────────────────────┤
    │   TextField       │     Preview         │
    │   (Editor)        │   (Markdown)        │
    │                   │   [visible=p_on]    │
    └───────────────────┴─────────────────────┘
    """

    _MAX_AUTO_TITLE_WORDS: int = 4

    def __init__(self, tab_index: int) -> None:
        """Inicializa a aba com índice sequencial.

        Args:
            tab_index: Número sequencial da aba (1-based) usado para o título padrão.
        """
        self._tab_index: int = tab_index
        self._title_edited_manually: bool = False
        self._first_insert: bool = True
        self._preview_visible: bool = False

        # Campo de título (cabeçalho da aba)
        self._header_field = ft.TextField(
            value=f"Transcrição {tab_index}",
            border=ft.InputBorder.NONE,
            bgcolor=ft.Colors.TRANSPARENT,
            color=ft.Colors.WHITE,
            text_size=13,
            dense=True,
            content_padding=ft.padding.symmetric(horizontal=6, vertical=0),
            width=110,
            cursor_color=ft.Colors.BLUE_300,
            on_change=self._on_title_change,
        )

        # Campo de texto principal (editor)
        self._body = ft.TextField(
            multiline=True,
            expand=True,
            border=ft.InputBorder.NONE,
            bgcolor=ft.Colors.TRANSPARENT,
            focused_bgcolor=ft.Colors.TRANSPARENT,
            hint_text="Sua transcrição aparecerá aqui...",
            hint_style=ft.TextStyle(color="#6b7280"),
            text_size=15,
            cursor_color=ft.Colors.BLUE_300,
            on_change=self._on_body_change,
        )

        # Componente de preview
        self._preview = MarkdownPreview(
            debounce_ms=300,
            on_tap_link=self._on_preview_link_tap,
        )

        # Barra de ferramentas (recebe referência ao TextField)
        # TEMPORARIAMENTE DESABILITADA - aguardando correção do bug na função prefix_line
        self._toolbar = MarkdownToolbar(
            text_field=self._body,
            on_preview_toggle=self._on_preview_toggle,
        )
        self._toolbar.visible = False  # Esconde a toolbar temporariamente

        # Container do editor (lado esquerdo do split)
        self._editor_container = ft.Container(
            content=self._body,
            expand=True,
            bgcolor="#111827",
            border_radius=ft.border_radius.all(4),
            padding=ft.padding.all(8),
        )

        # Área de preview (lado direito do split, inicialmente oculta)
        self._preview_container = ft.Container(
            content=self._preview,
            expand=True,
            visible=False,
            bgcolor="#111827",
            border_radius=ft.border_radius.all(4),
            padding=ft.padding.all(8),
        )

        # Divisor entre editor e preview
        self._split_divider = ft.VerticalDivider(
            width=1,
            color="#374151",
            visible=False,
        )

        # Linha com split view (editor + preview)
        self._split_row = ft.Row(
            controls=[
                self._editor_container,
                self._split_divider,
                self._preview_container,
            ],
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        # Coluna principal: toolbar + área de edição
        self._editor_area = ft.Column(
            controls=[
                self._toolbar,
                ft.Divider(height=1, color="#374151"),
                self._split_row,
            ],
            expand=True,
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )

    # ------------------------------------------------------------------ #
    #  Propriedades públicas — expõem controles para injeção no ft.Tab    #
    # ------------------------------------------------------------------ #

    @property
    def header_control(self) -> ft.TextField:
        """Retorna o controle de cabeçalho para injeção em ``ft.Tab.label``."""
        return self._header_field

    @property
    def body_control(self) -> ft.Control:
        """Retorna o controle de corpo para injeção em ``ft.TabBarView.controls``.

        Retorna uma ``ft.Column`` composta com toolbar + área de edição,
        permitindo formatação Markdown e preview em tempo real.
        """
        return self._editor_area

    # ------------------------------------------------------------------ #
    #  API Pública                                                         #
    # ------------------------------------------------------------------ #

    def insert_text(self, chunk: str) -> None:
        """Insere um chunk de texto na área de transcrição desta aba.

        Na **primeira** inserção, se o usuário não tiver editado o título
        manualmente, renomeia a aba com as primeiras palavras do chunk.

        Utiliza ``update()`` de escopo local — nunca dispara re-render global.

        Atualiza também o preview se estiver visível.

        Args:
            chunk: Fragmento de texto transcrito a ser inserido.
        """
        if not chunk:
            return

        if self._first_insert and not self._title_edited_manually:
            self._apply_auto_title(chunk)
            self._first_insert = False

        current = self._body.value or ""
        separator = " " if current and not chunk.startswith(" ") else ""
        self._body.value = current + separator + chunk

        try:
            self._body.update()
        except Exception:
            pass

        # Atualiza preview se visível
        if self._preview_visible:
            self._preview.render(self._body.value or "")

    def get_text(self) -> str:
        """Retorna o conteúdo atual da área de transcrição."""
        return self._body.value or ""

    def clear(self) -> None:
        """Limpa o conteúdo da aba e reseta o estado de inserção.

        O título é resetado para o padrão somente se o usuário não
        o tiver editado manualmente.
        """
        self._body.value = ""
        self._first_insert = True

        if not self._title_edited_manually:
            self._header_field.value = f"Transcrição {self._tab_index}"
            try:
                self._header_field.update()
            except Exception:
                pass

        try:
            self._body.update()
        except Exception:
            pass

        # Limpa preview
        if self._preview_visible:
            self._preview.clear()

    # ------------------------------------------------------------------ #
    #  Handlers e métodos internos                                         #
    # ------------------------------------------------------------------ #

    def _on_title_change(self, e: ft.ControlEvent) -> None:
        """Marca que o usuário editou o título manualmente, bloqueando auto-rename."""
        self._title_edited_manually = True

    def _on_body_change(self, e: ft.ControlEvent) -> None:
        """Handler para mudanças no corpo do texto.

        Atualiza o preview em tempo real se estiver visível.
        """
        if self._preview_visible:
            self._preview.render(self._body.value or "")

    def _on_preview_toggle(self, active: bool) -> None:
        """Callback para toggle do preview.

        Args:
            active: Se o preview deve estar visível.
        """
        self._preview_visible = active

        # Atualiza visibilidade dos componentes
        self._preview_container.visible = active
        self._split_divider.visible = active

        # Se ativou preview, renderiza conteúdo atual
        if active:
            self._preview.render(self._body.value or "")

        try:
            self._split_row.update()
        except Exception:
            pass

    def _on_preview_link_tap(self, url: str) -> None:
        """Handler para cliques em links no preview.

        Args:
            url: URL do link clicado.
        """
        # Por enquanto apenas loga. Futuramente pode abrir browser.
        print(f"[Preview] Link clicado: {url}")

    def _apply_auto_title(self, source_text: str) -> None:
        """Extrai e aplica as primeiras palavras do texto como título da aba."""
        words = source_text.split()
        auto_title = " ".join(words[: self._MAX_AUTO_TITLE_WORDS])
        if auto_title:
            self._header_field.value = auto_title
            try:
                self._header_field.update()
            except Exception:
                pass
