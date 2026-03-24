"""Componente de aba individual de transcrição com estado completamente isolado.

Cada instância de AbaTranscricao é autossuficiente: gerencia seu próprio
campo de texto, seu próprio título editável e suas próprias flags de estado.
Nenhum dado vaza entre instâncias.
"""

from __future__ import annotations

import flet as ft


class AbaTranscricao:
    """Encapsula uma aba individual de transcrição com estado completamente isolado.

    Cada instância gerencia:
    - ``_header_field``: Campo de título editável inline (injetado em ``ft.Tab.label``).
    - ``_body``: Campo de texto multilinhas (injetado em ``ft.TabBarView.controls``).
    - Flags de controle: ``_title_edited_manually`` e ``_first_insert``.

    A classe *não* herda de ``ft.Control`` diretamente para evitar registro duplo
    no widget tree do Flet. Os controles são expostos por propriedades e injetados
    externamente pelo ``TabManager``.
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

        self._body = ft.TextField(
            multiline=True,
            expand=True,
            border=ft.InputBorder.NONE,
            bgcolor=ft.Colors.TRANSPARENT,
            hint_text="Sua transcrição aparecerá aqui...",
            hint_style=ft.TextStyle(color="#6b7280"),
            text_size=15,
            min_lines=10,
            cursor_color=ft.Colors.BLUE_300,
        )

    # ------------------------------------------------------------------ #
    #  Propriedades públicas — expõem controles para injeção no ft.Tab    #
    # ------------------------------------------------------------------ #

    @property
    def header_control(self) -> ft.TextField:
        """Retorna o controle de cabeçalho para injeção em ``ft.Tab.label``."""
        return self._header_field

    @property
    def body_control(self) -> ft.TextField:
        """Retorna o controle de corpo para injeção em ``ft.TabBarView.controls``."""
        return self._body

    # ------------------------------------------------------------------ #
    #  API Pública                                                         #
    # ------------------------------------------------------------------ #

    def insert_text(self, chunk: str) -> None:
        """Insere um chunk de texto na área de transcrição desta aba.

        Na **primeira** inserção, se o usuário não tiver editado o título
        manualmente, renomeia a aba com as primeiras palavras do chunk.

        Utiliza ``update()`` de escopo local — nunca dispara re-render global.

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

    # ------------------------------------------------------------------ #
    #  Handlers e métodos internos                                         #
    # ------------------------------------------------------------------ #

    def _on_title_change(self, e: ft.ControlEvent) -> None:
        """Marca que o usuário editou o título manualmente, bloqueando auto-rename."""
        self._title_edited_manually = True

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
