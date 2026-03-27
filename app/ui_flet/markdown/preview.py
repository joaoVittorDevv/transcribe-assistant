"""Componente de preview Markdown com renderização otimizada.

Fornece um wrapper em torno de ``ft.Markdown`` com:
- Debouncing para evitar re-renderizações excessivas
- Suporte a links clicáveis
- Configuração otimizada para GitHub-Flavored Markdown
"""

from __future__ import annotations

import threading
from typing import Callable

import flet as ft


class MarkdownPreview(ft.Container):
    """Wrapper para ``ft.Markdown`` com renderização debounced.

    O componente evita atualizações excessivas do preview utilizando um timer
    que aguarda um intervalo de inatividade antes de renderizar. Isso é
    especialmente importante durante streaming de texto da transcrição.

    Attributes:
        debounce_ms: Intervalo de debounce em milissegundos (padrão: 300ms).
    """

    DEFAULT_DEBOUNCE_MS: int = 300

    def __init__(
        self,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
        on_tap_link: Callable[[str], None] | None = None,
    ) -> None:
        """Inicializa o componente de preview.

        Args:
            debounce_ms: Intervalo de debounce em milissegundos.
            on_tap_link: Callback chamado quando um link é clicado (recebe a URL).
        """
        super().__init__()
        self.expand = True
        self.visible = False
        self.bgcolor = "#1f2937"
        self.border_radius = 8
        self.padding = ft.padding.all(16)
        self.border = ft.border.all(1, "#374151")

        self._debounce_ms = debounce_ms
        self._on_tap_link = on_tap_link
        self._debounce_timer: threading.Timer | None = None
        self._pending_text: str = ""
        self._is_rendering: bool = False

        self._markdown = ft.Markdown(
            value="",
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            on_tap_link=self._handle_tap_link,
            shrink_wrap=True,
        )

        self.content = ft.Column(
            controls=[self._markdown],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def _handle_tap_link(self, e: ft.ControlEvent) -> None:
        """Trata cliques em links do Markdown."""
        if self._on_tap_link and hasattr(e, "data") and e.data:
            self._on_tap_link(e.data)

    def render(self, markdown_text: str) -> None:
        """Agenda a renderização do texto Markdown com debounce.

        Em vez de renderizar imediatamente, este método agenda uma atualização
        após o intervalo de debounce. Chamadas subsequentes cancelam o timer
        anterior, garantindo que apenas a última atualização seja processada.

        Args:
            markdown_text: Texto Markdown a ser renderizado.
        """
        self._pending_text = markdown_text

        # Cancela timer anterior se existir
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()

        # Agenda nova renderização
        self._debounce_timer = threading.Timer(
            self._debounce_ms / 1000.0,
            self._do_render,
        )
        self._debounce_timer.daemon = True
        self._debounce_timer.start()

    def _do_render(self) -> None:
        """Executa a renderização efetiva do Markdown.

        Este método é chamado pelo timer de debounce e atualiza o componente
        de forma thread-safe.
        """
        if self._is_rendering:
            return

        self._is_rendering = True
        try:
            self._markdown.value = self._pending_text
            if self.visible:
                self._markdown.update()
        except Exception:
            pass
        finally:
            self._is_rendering = False

    def render_immediate(self, markdown_text: str) -> None:
        """Renderiza o Markdown imediatamente, sem debounce.

        Use com cautela - preferir ``render()`` para atualizações frequentes.

        Args:
            markdown_text: Texto Markdown a ser renderizado.
        """
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None

        self._pending_text = markdown_text
        self._markdown.value = markdown_text

        try:
            if self.visible:
                self._markdown.update()
        except Exception:
            pass

    def show(self) -> None:
        """Torna o preview visível."""
        self.visible = True
        try:
            self.update()
        except Exception:
            pass

    def hide(self) -> None:
        """Oculta o preview."""
        self.visible = False
        try:
            self.update()
        except Exception:
            pass

    def toggle(self) -> bool:
        """Alterna a visibilidade do preview.

        Returns:
            Novo estado de visibilidade (True = visível, False = oculto).
        """
        if self.visible:
            self.hide()
            return False
        else:
            self.show()
            return True

    def clear(self) -> None:
        """Limpa o conteúdo do preview."""
        self._pending_text = ""
        self._markdown.value = ""
        try:
            self._markdown.update()
        except Exception:
            pass

    def dispose(self) -> None:
        """Libera recursos do componente."""
        if self._debounce_timer is not None:
            self._debounce_timer.cancel()
            self._debounce_timer = None
