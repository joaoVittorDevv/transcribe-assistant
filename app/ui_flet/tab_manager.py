"""Gerenciador de abas dinâmicas de transcrição.

Utiliza a API correta do Flet 0.82.2:
- ``ft.Tabs``     → contêiner pai (content + length + selected_index)
- ``ft.TabBar``   → barra com lista de ``ft.Tab`` (label aceita Control)
- ``ft.TabBarView`` → corpo com lista de Controls (um por aba)

Cada ``AbaTranscricao`` é instância completamente isolada.
"""

from __future__ import annotations

import flet as ft

from app.ui_flet.tab_transcription import AbaTranscricao


class TabManager(ft.Container):
    """Gerencia a criação dinâmica e o ciclo de vida de múltiplas ``AbaTranscricao``.

    A arquitetura segue o padrão Flet 0.82.2:

    .. code-block:: text

        TabManager (ft.Container)
        └── ft.Tabs
            ├── ft.TabBar (tabs=[ft.Tab(label=header_field), ..., ft.Tab(label=Icon+Text)])
            └── ft.TabBarView (controls=[body_control, ..., empty_container])

    O índice da aba "Nova" é sempre o último. O ``on_change`` no ``ft.Tabs``
    detecta quando ele é selecionado e cria uma nova aba.

    Usage::

        manager = TabManager(page)
        manager.add_tab()                       # cria a primeira aba
        manager.insert_text_active("texto...")  # insere na aba ativa
    """

    def __init__(self, page: ft.Page) -> None:
        """Inicializa o gerenciador com ``ft.Tabs`` vazio (somente a aba "Nova").

        Args:
            page: Referência à ``ft.Page`` do Flet.
        """
        super().__init__()
        self.expand = True
        self._page = page
        self._abas: list[AbaTranscricao] = []

        # TabBar: lista de ft.Tab (cabeçalhos)
        self._tab_bar = ft.TabBar(
            tabs=[self._build_add_tab_header()],
            scrollable=True,
            tab_alignment=ft.TabAlignment.START,
            indicator_color=ft.Colors.BLUE_400,
            label_color=ft.Colors.WHITE,
            unselected_label_color=ft.Colors.GREY_500,
        )

        # TabBarView: lista de bodies (um por aba)
        self._tab_view = ft.TabBarView(
            controls=[ft.Container()],  # Placeholder para a aba "Nova"
            expand=True,
        )

        # Tabs: orquestrador pai
        self._tabs = ft.Tabs(
            content=ft.Column(
                controls=[
                    self._tab_bar,
                    ft.Divider(height=1, color="#374151"),
                    self._tab_view,
                ],
                expand=True,
                spacing=0,
            ),
            length=1,
            selected_index=0,
            on_change=self._on_tab_change,
            animation_duration=ft.Duration(milliseconds=150),
        )

        self.content = self._tabs

    # ------------------------------------------------------------------ #
    #  API Pública                                                         #
    # ------------------------------------------------------------------ #

    def add_tab(self) -> AbaTranscricao:
        """Cria e adiciona uma nova ``AbaTranscricao`` ao gerenciador.

        A nova aba é inserida imediatamente antes da aba "Nova" e recebe
        o foco automaticamente.

        Returns:
            A instância ``AbaTranscricao`` recém-criada.
        """
        tab_index = len(self._abas) + 1
        aba = AbaTranscricao(tab_index=tab_index)
        self._abas.append(aba)

        # Cabeçalho: ft.Tab com label=Control (TextField + Botão X)
        close_btn = ft.IconButton(
            icon=ft.Icons.CLOSE,
            icon_size=12,
            icon_color=ft.Colors.GREY_500,
            tooltip="Fechar aba",
            on_click=lambda _: self.remove_tab(aba),
        )

        new_header = ft.Tab(
            label=ft.Row(
                controls=[aba.header_control, close_btn],
                spacing=0,
                alignment=ft.MainAxisAlignment.START,
                tight=True,
            )
        )

        # Body: Container com o TextField de transcrição
        new_body = ft.Container(
            content=aba.body_control,
            expand=True,
            padding=ft.padding.only(top=8, left=4, right=4),
            bgcolor="#111827",
        )

        # Insere antes do placeholder "Nova" (sempre o último)
        add_pos = len(self._tab_bar.tabs) - 1
        self._tab_bar.tabs.insert(add_pos, new_header)
        self._tab_view.controls.insert(add_pos, new_body)

        new_count = len(self._tab_bar.tabs)
        self._tabs.length = new_count
        self._tabs.selected_index = add_pos

        try:
            self._tabs.update()
        except Exception:
            pass

        return aba

    def remove_tab(self, aba: AbaTranscricao) -> None:
        """Remove uma aba do gerenciador e de todos os componentes visuais.

        Args:
            aba: A instância de ``AbaTranscricao`` que deve ser fechada.
        """
        try:
            # Encontrar o índice da aba na lista gerenciada (sem contar a aba 'Nova')
            idx = self._abas.index(aba)
        except ValueError:
            return

        # Sincronizar remoção nos 3 componentes
        self._abas.pop(idx)
        self._tab_bar.tabs.pop(idx)
        self._tab_view.controls.pop(idx)

        # Atualizar comprimento das abas
        new_count = len(self._tab_bar.tabs)
        self._tabs.length = new_count

        # Se removeu a aba que estava ativa, focar na anterior ou na próxima
        if idx >= new_count:
            res_idx = new_count - 1 if new_count > 0 else 0
        else:
            res_idx = idx

        self._tabs.selected_index = max(0, res_idx)

        try:
            self._tabs.update()
        except Exception:
            pass

    @property
    def active_tab(self) -> AbaTranscricao | None:
        """Retorna a ``AbaTranscricao`` correspondente à aba ativa.

        Returns:
            A instância ativa, ou ``None`` se a aba "Nova" estiver
            selecionada ou nenhuma aba de conteúdo existir.
        """
        idx = self._tabs.selected_index or 0
        if 0 <= idx < len(self._abas):
            return self._abas[idx]
        return None

    def insert_text_active(self, chunk: str) -> None:
        """Insere texto na aba atualmente ativa.

        Operação segura: silenciosamente ignorada se não há aba ativa.

        Args:
            chunk: Fragmento de texto transcrito a ser inserido.
        """
        tab = self.active_tab
        if tab is not None:
            tab.insert_text(chunk)

    # ------------------------------------------------------------------ #
    #  Internos                                                            #
    # ------------------------------------------------------------------ #

    def _build_add_tab_header(self) -> ft.Tab:
        """Cria o cabeçalho da aba especial 'Nova'."""
        return ft.Tab(
            label=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD, size=14, color=ft.Colors.BLUE_300),
                    ft.Text("Nova aba", size=12, color=ft.Colors.BLUE_300),
                ],
                spacing=4,
                tight=True,
            ),
        )

    def _on_tab_change(self, e: ft.ControlEvent) -> None:
        """Cria nova aba se o usuário selecionar a aba 'Nova'."""
        add_tab_position = len(self._tab_bar.tabs) - 1
        if self._tabs.selected_index == add_tab_position:
            self.add_tab()
