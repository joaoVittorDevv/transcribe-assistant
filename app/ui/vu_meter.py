"""app.ui.vu_meter — Animated VU Meter widget for CustomTkinter.

Displays a vertical bar that transitions from green to red as the
audio level rises. Updates are driven externally via set_level().
"""

import customtkinter as ctk

# Color stops: (threshold, hex_color)
_COLOR_STOPS = [
    (0.0, "#22c55e"),  # Green — silence / low level
    (0.6, "#eab308"),  # Yellow — moderate level
    (0.85, "#ef4444"),  # Red — high / clipping risk
]


def _interpolate_color(level: float) -> str:
    """Return a hex color interpolated across the VU color stops."""
    level = max(0.0, min(1.0, level))

    for i in range(len(_COLOR_STOPS) - 1):
        t_low, c_low = _COLOR_STOPS[i]
        t_high, c_high = _COLOR_STOPS[i + 1]
        if level <= t_high:
            ratio = (level - t_low) / (t_high - t_low) if t_high > t_low else 0.0
            return _blend_hex(c_low, c_high, ratio)

    return _COLOR_STOPS[-1][1]


def _blend_hex(c1: str, c2: str, ratio: float) -> str:
    """Linearly blend two hex colours by ratio (0.0 = c1, 1.0 = c2)."""

    def parse(c: str) -> tuple[int, int, int]:
        c = c.lstrip("#")
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)

    r1, g1, b1 = parse(c1)
    r2, g2, b2 = parse(c2)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


class VUMeter(ctk.CTkFrame):
    """Animated vertical VU meter widget.

    Args:
        master:      Parent widget.
        width:       Widget width in pixels.
        height:      Widget height in pixels.
        **kwargs:    Passed to CTkFrame.
    """

    def __init__(
        self,
        master,
        width: int = 30,
        height: int = 120,
        **kwargs,
    ) -> None:
        kwargs.setdefault("fg_color", "transparent")
        super().__init__(master, width=width, height=height, **kwargs)

        self._level: float = 0.0
        self._canvas_width = width
        self._canvas_height = height

        self._canvas = ctk.CTkCanvas(
            self,
            width=width,
            height=height,
            bg="#1a1a2e",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)

        # Draw initial empty bar
        self._bar_id = self._canvas.create_rectangle(
            0,
            height,
            width,
            height,
            fill="#22c55e",
            outline="",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_level(self, level: float) -> None:
        """Update the bar height. level must be in [0.0, 1.0].

        This method is NOT thread-safe — call it from the UI thread only
        (e.g., via root.after()).
        """
        self._level = max(0.0, min(1.0, level))
        self._redraw()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _redraw(self) -> None:
        h = self._canvas_height
        w = self._canvas_width
        bar_top = int(h * (1.0 - self._level))
        color = _interpolate_color(self._level)

        self._canvas.coords(self._bar_id, 0, bar_top, w, h)
        self._canvas.itemconfig(self._bar_id, fill=color)
