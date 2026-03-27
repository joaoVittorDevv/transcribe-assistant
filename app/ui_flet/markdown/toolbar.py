"""Barra de ferramentas Markdown para formatação de texto.

Fornece botões para aplicar formatação Markdown a um ``ft.TextField``:
- Formatação inline: Negrito, Itálico, Tachado, Código, Link
- Cabeçalhos: H1, H2, H3
- Blocos: Lista com marcadores, Lista numerada, Blockquote
- Inserções: Linha horizontal
- Toggle de Preview
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import flet as ft

from app.ui_flet.markdown import text_utils

if TYPE_CHECKING:
    pass


class MarkdownToolbar(ft.Container):
    """Barra de ferramentas com botões de formatação Markdown.

    Opera sobre uma referência a um ``ft.TextField``, lendo a seleção atual
    e aplicando a formatação apropriada através das funções de ``text_utils``.

    Attributes:
        on_preview_toggle: Callback chamado quando o botão de preview é clicado.
    """

    # Cores do tema
    _BTN_BG_COLOR: str = "#374151"
    _BTN_HOVER_COLOR: str = "#4b5563"
    _BTN_ACTIVE_COLOR: str = "#3b82f6"
    _BTN_ICON_COLOR: str = "#d1d5db"
    _BTN_ICON_ACTIVE_COLOR: str = "#60a5fa"
    _TOOLBAR_BG_COLOR: str = "#1f2937"

    def __init__(
        self,
        text_field: ft.TextField,
        on_preview_toggle: Callable[[bool], None] | None = None,
    ) -> None:
        """Inicializa a barra de ferramentas.

        Args:
            text_field: Referência ao TextField que será manipulado.
            on_preview_toggle: Callback para quando o preview for alternado.
        """
        super().__init__()
        self._text_field = text_field
        self._on_preview_toggle = on_preview_toggle
        self._preview_active: bool = False

        self.bgcolor = self._TOOLBAR_BG_COLOR
        self.border_radius = ft.border_radius.all(6)
        self.padding = ft.padding.symmetric(horizontal=8, vertical=4)

        self.content = self._build_toolbar()
        self._preview_btn: ft.IconButton | None = None

    def _build_toolbar(self) -> ft.Row:
        """Constrói os botões da barra de ferramentas."""
        buttons: list[ft.Control] = [
            # Formatação inline
            self._create_btn(ft.Icons.FORMAT_BOLD, "Negrito (**)", self._on_bold),
            self._create_btn(ft.Icons.FORMAT_ITALIC, "Itálico (_)", self._on_italic),
            self._create_btn(
                ft.Icons.FORMAT_STRIKETHROUGH,
                "Tachado (~~)",
                self._on_strikethrough,
            ),
            self._create_btn(
                ft.Icons.CODE,
                "Código inline (`)",
                self._on_code,
            ),
            self._create_btn(ft.Icons.LINK, "Link", self._on_link),
            ft.VerticalDivider(width=1, color="#374151", visible=False),
            # Cabeçalhos
            self._create_btn(
                ft.Icons.TITLE,
                "Título 1 (#)",
                self._on_h1,
                icon_size=18,
            ),
            self._create_btn(
                ft.Icons.TITLE,
                "Título 2 (##)",
                self._on_h2,
                icon_size=16,
            ),
            self._create_btn(
                ft.Icons.TITLE,
                "Título 3 (###)",
                self._on_h3,
                icon_size=14,
            ),
            ft.VerticalDivider(width=1, color="#374151"),
            # Listas e blocos
            self._create_btn(
                ft.Icons.FORMAT_LIST_BULLETED,
                "Lista com marcadores",
                self._on_bullet_list,
            ),
            self._create_btn(
                ft.Icons.FORMAT_LIST_NUMBERED,
                "Lista numerada",
                self._on_numbered_list,
            ),
            self._create_btn(
                ft.Icons.FORMAT_QUOTE,
                "Citação (blockquote)",
                self._on_blockquote,
            ),
            ft.VerticalDivider(width=1, color="#374151"),
            # Inserções
            self._create_btn(
                ft.Icons.HORIZONTAL_RULE,
                "Linha horizontal",
                self._on_horizontal_rule,
            ),
            ft.VerticalDivider(width=1, color="#374151"),
            # Preview toggle
            self._create_preview_btn(),
        ]

        return ft.Row(
            controls=buttons,
            spacing=2,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _create_btn(
        self,
        icon: str,
        tooltip: str,
        on_click: Callable[[ft.ControlEvent], None],
        icon_size: int = 20,
    ) -> ft.IconButton:
        """Cria um botão de ícone padrão."""
        return ft.IconButton(
            icon=icon,
            icon_size=icon_size,
            icon_color=self._BTN_ICON_COLOR,
            tooltip=tooltip,
            on_click=on_click,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
                    ft.ControlState.HOVERED: self._BTN_HOVER_COLOR,
                },
            ),
        )

    def _create_preview_btn(self) -> ft.IconButton:
        """Cria o botão de toggle do preview."""
        self._preview_btn = ft.IconButton(
            icon=ft.Icons.VISIBILITY,
            icon_size=20,
            icon_color=self._BTN_ICON_COLOR,
            tooltip="Alternar preview",
            on_click=self._on_preview_toggle,
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.TRANSPARENT,
                    ft.ControlState.HOVERED: self._BTN_HOVER_COLOR,
                    ft.ControlState.SELECTED: self._BTN_ACTIVE_COLOR,
                },
            ),
        )
        return self._preview_btn

    # ----------------------------------------------------------------------- #
    #  Métodos auxiliares de manipulação de texto                            #
    # ----------------------------------------------------------------------- #

    def _get_selection(self) -> tuple[int, int]:
        """Obtém os offsets de seleção do TextField.

        Returns:
            Tupla (start, end) com os índices de seleção.
            Se não houver seleção, retorna (len(text), len(text)) para
            inserção no final do texto existente.
        """
        selection = self._text_field.selection
        if selection is not None and len(selection) >= 2:
            start, end = selection[0], selection[1]
            # Garante que start <= end
            if start > end:
                start, end = end, start
            return start, end

        # Sem seleção: insere no final do texto
        # Nota: Flet TextField não expõe cursor_position diretamente
        text_len = len(self._text_field.value or "")
        return text_len, text_len

    def _apply_format(
        self,
        format_func: Callable[[str, int, int], tuple[str, int, int]],
    ) -> None:
        """Aplica uma função de formatação ao texto selecionado.

        Args:
            format_func: Função que recebe (text, start, end) e retorna
                (new_text, new_start, new_end).
        """
        text = self._text_field.value or ""
        start, end = self._get_selection()

        new_text, new_start, new_end = format_func(text, start, end)

        self._text_field.value = new_text
        self._text_field.cursor_position = new_end
        self._text_field.selection = (new_start, new_end)

        try:
            self._text_field.update()
        except Exception:
            pass

    def _apply_insert(
        self,
        insert_func: Callable[[str, int], tuple[str, int, int]],
    ) -> None:
        """Aplica uma função de inserção na posição do cursor.

        Args:
            insert_func: Função que recebe (text, position) e retorna
                (new_text, new_start, new_end).
        """
        text = self._text_field.value or ""
        start, _ = self._get_selection()

        new_text, new_start, new_end = insert_func(text, start)

        self._text_field.value = new_text
        self._text_field.cursor_position = new_end

        try:
            self._text_field.update()
        except Exception:
            pass

    # ----------------------------------------------------------------------- #
    #  Handlers dos botões de formatação                                      #
    # ----------------------------------------------------------------------- #

    def _on_bold(self, e: ft.ControlEvent) -> None:
        """Aplica formatação negrito."""
        self._apply_format(text_utils.apply_bold)

    def _on_italic(self, e: ft.ControlEvent) -> None:
        """Aplica formatação itálico."""
        self._apply_format(text_utils.apply_italic)

    def _on_strikethrough(self, e: ft.ControlEvent) -> None:
        """Aplica formatação tachado."""
        self._apply_format(text_utils.apply_strikethrough)

    def _on_code(self, e: ft.ControlEvent) -> None:
        """Aplica formatação código inline."""
        self._apply_format(text_utils.apply_code)

    def _on_link(self, e: ft.ControlEvent) -> None:
        """Aplica formatação de link."""
        self._apply_format(text_utils.apply_link)

    def _on_h1(self, e: ft.ControlEvent) -> None:
        """Aplica cabeçalho nível 1."""
        self._apply_format(lambda t, s, e: text_utils.apply_heading(t, s, e, 1))

    def _on_h2(self, e: ft.ControlEvent) -> None:
        """Aplica cabeçalho nível 2."""
        self._apply_format(lambda t, s, e: text_utils.apply_heading(t, s, e, 2))

    def _on_h3(self, e: ft.ControlEvent) -> None:
        """Aplica cabeçalho nível 3."""
        self._apply_format(lambda t, s, e: text_utils.apply_heading(t, s, e, 3))

    def _on_bullet_list(self, e: ft.ControlEvent) -> None:
        """Aplica lista com marcadores."""
        self._apply_format(text_utils.apply_bullet_list)

    def _on_numbered_list(self, e: ft.ControlEvent) -> None:
        """Aplica lista numerada."""
        self._apply_format(text_utils.apply_numbered_list)

    def _on_blockquote(self, e: ft.ControlEvent) -> None:
        """Aplica blockquote."""
        self._apply_format(text_utils.apply_blockquote)

    def _on_horizontal_rule(self, e: ft.ControlEvent) -> None:
        """Insere linha horizontal."""
        self._apply_insert(text_utils.insert_horizontal_rule)

    def _on_preview_toggle(self, e: ft.ControlEvent) -> None:
        """Alterna o estado do preview."""
        self._preview_active = not self._preview_active

        # Atualiza aparência do botão
        if self._preview_btn is not None:
            self._preview_btn.icon = (
                ft.Icons.VISIBILITY_OFF
                if self._preview_active
                else ft.Icons.VISIBILITY
            )
            self._preview_btn.icon_color = (
                self._BTN_ICON_ACTIVE_COLOR
                if self._preview_active
                else self._BTN_ICON_COLOR
            )
            try:
                self._preview_btn.update()
            except Exception:
                pass

        # Notifica callback externo
        if self._on_preview_toggle is not None:
            self._on_preview_toggle(self._preview_active)

    # ----------------------------------------------------------------------- #
    #  API Pública                                                            #
    # ----------------------------------------------------------------------- #

    @property
    def preview_active(self) -> bool:
        """Retorna se o preview está ativo."""
        return self._preview_active

    def set_preview_state(self, active: bool) -> None:
        """Define o estado do preview programaticamente."""
        if self._preview_active != active:
            self._preview_active = active
            if self._preview_btn is not None:
                self._preview_btn.icon = (
                    ft.Icons.VISIBILITY_OFF
                    if self._preview_active
                    else ft.Icons.VISIBILITY
                )
                self._preview_btn.icon_color = (
                    self._BTN_ICON_ACTIVE_COLOR
                    if self._preview_active
                    else self._BTN_ICON_COLOR
                )
                try:
                    self._preview_btn.update()
                except Exception:
                    pass
