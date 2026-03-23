"""app.ui_flet.vu_meter — Medidor de Volume para Flet."""

import flet as ft

_COLOR_STOPS = [
    (0.0, "#22c55e"),  # Green 
    (0.6, "#eab308"),  # Yellow 
    (0.85, "#ef4444"), # Red
]

def _blend_hex(c1: str, c2: str, ratio: float) -> str:
    """Mescla duas cores hexagonais com base na proporção (0.0 a 1.0)."""
    def parse(c: str) -> tuple[int, int, int]:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    r1, g1, b1 = parse(c1)
    r2, g2, b2 = parse(c2)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"

def _interpolate_color(level: float) -> str:
    level = max(0.0, min(1.0, level))
    for i in range(len(_COLOR_STOPS) - 1):
        t_low, c_low = _COLOR_STOPS[i]
        t_high, c_high = _COLOR_STOPS[i + 1]
        if level <= t_high:
            ratio = (level - t_low) / (t_high - t_low) if t_high > t_low else 0.0
            return _blend_hex(c_low, c_high, ratio)
    return _COLOR_STOPS[-1][1]


class VUMeter(ft.Container):
    def __init__(self, width=30, height=80):
        super().__init__()
        self.width = width
        self.height = height
        self.bgcolor = "#1a1a2e"
        self.border_radius = 4
        self.clip_behavior = ft.ClipBehavior.HARD_EDGE
        
        self.bar = ft.Container(
            width=width,
            height=0,
            bgcolor="#22c55e"
        )
        
        # O Stack alinha o Container interior no bottom
        self.content = ft.Stack(
            controls=[
                # Um wrapper Container encarregado do alinhamento bottom
                ft.Container(
                    content=self.bar,
                    alignment=ft.alignment.Alignment(0, 1),
                    width=width,
                    height=height
                )
            ],
            width=width,
            height=height
        )

    def set_level(self, level: float):
        level = max(0.0, min(1.0, level))
        h = int(self.height * level)
        self.bar.height = h
        self.bar.bgcolor = _interpolate_color(level)
        try:
            self.bar.update()
        except Exception:
            pass
