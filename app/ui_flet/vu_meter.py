"""app.ui_flet.vu_meter — Componente VU Meter estilo LED para Flet 0.82.x.

Implementa um medidor de volume com LEDs discretos que transitam suavemente
entre "apagado" e "aceso" usando a animação implícita nativa do Flet.

Notas de implementação (Flet 0.82.2):
    - ft.Control.update() envia delta apenas do próprio controle; filhos
      com propriedades alteradas NÃO são propagados automaticamente.
      Solução: chamar page.update() via referência armazenada,
      ou atualizar cada LED individualmente. Optamos por page.update()
      pois é o mecanismo oficial para updates multi-controle.

    - Cada ft.Container DEVE ter sua própria instância de ft.Animation
      (não compartilhada) para que o Flet gerencie a interpolação
      de cor por controle de forma independente.

    - O callback de áudio (sounddevice) roda em thread C de alta prioridade.
      page.update() é thread-safe no Flet e pode ser chamado de qualquer
      thread sem bloqueio da UI.
"""

from __future__ import annotations

import flet as ft

# ---------------------------------------------------------------------------
# Zonas de cor (proporção 0.0–1.0 relativa ao total de LEDs)
# ---------------------------------------------------------------------------

_ZONE_GREEN_END: float = 0.60  # 0%–60%  → Verde (seguro)
_ZONE_YELLOW_END: float = 0.85  # 60%–85% → Âmbar (atenção)
#                                # 85%–100%→ Vermelho (pico)

# Cores "acesas" por zona — paleta técnica/hardware
_COLOR_ON_GREEN: str = "#22c55e"  # Verde vibrante
_COLOR_ON_YELLOW: str = "#f59e0b"  # Âmbar quente
_COLOR_ON_RED: str = "#ef4444"  # Vermelho de pico

# Cor "apagada" — neutro escuro (dark mode compatível)
_COLOR_OFF: str = "#1f2937"

# Animação: rápida o suficiente para streams de áudio (~20fps), sem piscar
_ANIM_DURATION_MS: int = 60


def _led_color(index: int, total: int, active: int) -> str:
    """Retorna a cor correta para um LED dado seu índice e o nível atual.

    Args:
        index: Posição do LED (0 = esquerda).
        total: Total de LEDs no medidor.
        active: Quantidade de LEDs acesos no momento.

    Returns:
        String hexadecimal da cor BGR do Container.
    """
    if index >= active:
        return _COLOR_OFF

    ratio: float = (index + 1) / total
    if ratio <= _ZONE_GREEN_END:
        return _COLOR_ON_GREEN
    if ratio <= _ZONE_YELLOW_END:
        return _COLOR_ON_YELLOW
    return _COLOR_ON_RED


class VuMeter(ft.Row):
    """Medidor de volume estilo LED discreto para interfaces Flet.

    Cada LED é um ft.Container independente com ``animate`` próprio,
    garantindo transições de cor suaves via interpolação implícita do Flet.

    A referência à ``page`` é injetada via ``did_mount`` (ciclo de vida
    nativo do Flet), eliminando a necessidade de passagem manual no __init__
    e garantindo que ``page.update()`` só seja chamado após o controle
    estar de fato montado na árvore de widgets.

    Attributes:
        _leds: Lista de ft.Container representando cada LED.
        _num_leds: Quantidade total de LEDs.
        _last_active: Cache da última contagem ativa (evita re-renders
                      redundantes quando o nível de áudio não muda).
        _page_ref: Referência à ft.Page injetada em did_mount.

    Example::

        meter = VuMeter(num_leds=20, led_width=8, led_height=20)
        page.add(meter)

        # Em qualquer thread (callback de áudio):
        meter.set_level(0.73)
    """

    def __init__(
        self,
        num_leds: int = 20,
        led_width: int = 8,
        led_height: int = 20,
        spacing: int = 2,
    ) -> None:
        """Constrói o medidor criando N containers (LEDs) independentes.

        Args:
            num_leds: Número de segmentos LED. Padrão: 20.
            led_width: Largura de cada LED em pixels. Padrão: 8.
            led_height: Altura de cada LED em pixels. Padrão: 20.
            spacing: Gap horizontal entre LEDs em pixels. Padrão: 2.
        """
        self._num_leds: int = num_leds
        self._last_active: int = -1  # -1 força o primeiro render
        self._page_ref: ft.Page | None = None

        # IMPORTANTE: cada LED recebe sua PRÓPRIA instância de ft.Animation.
        # Compartilhar um único objeto causa conflito no estado de animação
        # interno do Flet (a animação de um LED sobrescreve a dos outros).
        self._leds: list[ft.Container] = [
            ft.Container(
                width=led_width,
                height=led_height,
                bgcolor=_COLOR_OFF,
                border_radius=2,
                animate=ft.Animation(
                    duration=_ANIM_DURATION_MS,
                    curve=ft.AnimationCurve.EASE_OUT,
                ),
            )
            for _ in range(num_leds)
        ]

        super().__init__(
            controls=self._leds,
            spacing=spacing,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def did_mount(self) -> None:
        """Ciclo de vida Flet: chamado quando o controle é adicionado à Page.

        Captura a referência à Page aqui, pois neste ponto o controle
        já está vinculado e ``self.page`` está disponível com segurança.
        """
        self._page_ref = self.page

    def will_unmount(self) -> None:
        """Ciclo de vida Flet: chamado antes de o controle ser removido.

        Limpa a referência à Page para evitar chamadas a um objeto inválido
        de threads de áudio que possam ainda estar rodando.
        """
        self._page_ref = None

    def set_level(self, level: float) -> None:
        """Atualiza o display do medidor com base no nível de áudio recebido.

        Seguro para chamada a partir de qualquer thread (incluindo o callback
        de alta prioridade do sounddevice). O ``page.update()`` do Flet é
        thread-safe e propaga os deltas de todos os filhos alterados de uma vez.

        O guard ``_last_active`` evita round-trips desnecessários ao frontend
        quando o nível de áudio oscila mas a contagem de LEDs acesos não muda.

        Args:
            level: Nível de áudio normalizado em [0.0, 1.0]. Valores fora
                   do intervalo são limitados automaticamente (clamp).
        """
        if self._page_ref is None:
            return  # Ainda não montado ou já desmontado

        clamped: float = max(0.0, min(1.0, level))
        active_count: int = round(clamped * self._num_leds)

        if active_count == self._last_active:
            return  # Sem mudança visual — skipa o update

        self._last_active = active_count

        for index, led in enumerate(self._leds):
            led.bgcolor = _led_color(index, self._num_leds, active_count)

        try:
            # page.update() propaga os deltas de todos os LEDs alterados
            # em uma única mensagem ao frontend — mais eficiente que
            # chamar led.update() N vezes individualmente.
            self._page_ref.update()
        except Exception:
            # page pode ter sido fechada enquanto o áudio ainda gravava
            self._page_ref = None

    def reset(self) -> None:
        """Apaga todos os LEDs e limpa o cache de estado.

        Deve ser chamado ao parar a gravação para zerar o medidor.
        O ``_last_active`` é resetado para -1 para forçar re-render
        no próximo ``set_level()``.
        """
        self._last_active = -1
        self.set_level(0.0)
