"""app.utils.tray_manager — Management for the System Tray (Indicator Applet).

Allows the app to display a dynamic status icon in the Ubuntu top panel and handle
actions like stopping recording or restoring focus when minimized.
"""

import os
from pathlib import Path
from typing import Callable, Optional
from PIL import Image, ImageDraw

# Try importing pystray, degrade gracefully if not installed
try:
    import pystray
    from pystray import MenuItem as item
    PYS_AVAILABLE = True
except ImportError:
    pystray = None
    item = None
    PYS_AVAILABLE = False

import app.config as config


class TrayManager:
    """Manages the lifecycle, icons, and menus of the System Tray integration."""

    _instance: Optional["TrayManager"] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TrayManager, cls).__new__(cls)
        return cls._instance

    def __init__(
        self,
        on_restore_clicked: Optional[Callable[[], None]] = None,
        on_stop_clicked: Optional[Callable[[], None]] = None,
        on_pause_clicked: Optional[Callable[[], None]] = None,
        on_exit_clicked: Optional[Callable[[], None]] = None
    ) -> None:
        # Avoid re-initialization if already setup
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._on_restore_clicked = on_restore_clicked
        self._on_stop_clicked = on_stop_clicked
        self._on_pause_clicked = on_pause_clicked
        self._on_exit_clicked = on_exit_clicked

        self._tray_icon: Optional[pystray.Icon] = None
        self._state: str = "idle"  # States: idle, recording, transcribing, error
        self._recording_is_paused: bool = False
        self._initialized: bool = True

        # Pre-generate state icons using Pillow
        self._icons = self._generate_state_icons()

    def is_available(self) -> bool:
        """Return True if pystray package is installed and usable."""
        return PYS_AVAILABLE

    def start(self) -> None:
        """Start the System Tray icon in a background thread."""
        if not self.is_available() or not config.TRAY_ENABLED:
            return

        if self._tray_icon is not None:
            return  # Already running

        try:
            menu = self._build_menu()
            # Set initial icon
            initial_icon = self._icons.get(self._state, self._icons["idle"])

            self._tray_icon = pystray.Icon(
                "transcribe-assistant",
                icon=initial_icon,
                title="Transcribe Assistant",
                menu=menu
            )

            # Assign left-click double/single tap actions to restore window (if supported by OS)
            self._tray_icon.activated = lambda reason: self._restore_app()

            # Run in a background thread natively supported by pystray
            self._tray_icon.run_detached()
        except Exception as e:
            print(f"[TRAY MANAGER] Failed to start system tray icon: {e}")

    def stop(self) -> None:
        """Stop the System Tray icon and clean up resources."""
        if self._tray_icon is not None:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None

    def update_state(self, state: str, is_paused: bool = False) -> None:
        """Update the internal state of the app and change the tray icon dynamically.

        Args:
            state (str): One of 'idle', 'recording', 'transcribing', 'error'.
            is_paused (bool): True if the recording is currently paused.
        """
        if state not in ["idle", "recording", "transcribing", "error"]:
            return

        self._state = state
        self._recording_is_paused = is_paused

        if not self.is_available() or self._tray_icon is None:
            return

        # Update the tray icon image based on state
        new_icon = self._icons.get(state, self._icons["idle"])
        self._tray_icon.icon = new_icon

        # Re-build the menu to reflect dynamic states (recording vs idle)
        self._tray_icon.menu = self._build_menu()

    def _generate_state_icons(self) -> dict:
        """Generate/load images for all application states."""
        icons = {}
        project_root = Path(__file__).parent.parent.parent
        logo_path = project_root / "assets" / "assist_transcribe_1x1.png"

        # Try to load base logo to superimpose status indicator, fallback to solid shapes
        base_logo = None
        if logo_path.exists():
            try:
                base_logo = Image.open(logo_path).resize((64, 64))
            except Exception:
                pass

        states = {
            "idle": {"color": (150, 150, 150), "badge": False},        # Gray / Inactive
            "recording": {"color": (239, 91, 91), "badge": True},       # Pastel Red
            "transcribing": {"color": (250, 204, 21), "badge": True},   # Yellow/Amber
            "error": {"color": (220, 38, 38), "badge": True}            # Strong Red
        }

        for state, conf in states.items():
            img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            if base_logo and state == "idle":
                # Ready/Idle uses the clean original logo
                img = base_logo.copy()
            elif base_logo and conf["badge"]:
                # Active states superimpose a status badge in the bottom-right corner
                img = base_logo.copy()
                draw_badge = ImageDraw.Draw(img)
                # Outer white border for contrast
                draw_badge.ellipse((40, 40, 62, 62), fill=(255, 255, 255))
                # Inner status badge
                draw_badge.ellipse((42, 42, 60, 60), fill=conf["color"])
                
                # Draw white exclamation mark inside the error badge
                if state == "error":
                    draw_badge.rectangle((49, 45, 53, 52), fill=(255, 255, 255))
                    draw_badge.rectangle((49, 54, 53, 57), fill=(255, 255, 255))
            else:
                # Solid fallback circles if base logo is missing
                draw.ellipse((8, 8, 56, 56), fill=conf["color"])
                draw.ellipse((6, 6, 58, 58), outline=(255, 255, 255), width=2)
                
                if state == "error":
                    # Draw a white exclamation mark
                    draw.rectangle((29, 18, 35, 42), fill=(255, 255, 255))
                    draw.rectangle((29, 46, 35, 52), fill=(255, 255, 255))

            icons[state] = img

        return icons

    def _build_menu(self) -> pystray.Menu:
        """Create the dynamic context menu for the system tray."""
        menu_items = []

        # 1. Restore action (always top)
        menu_items.append(item("Exibir Assistente", lambda: self._restore_app(), default=True))

        # 2. Recording-specific actions
        if self._state == "recording":
            pause_label = "Retomar Gravação" if self._recording_is_paused else "Pausar Gravação"
            menu_items.append(item(pause_label, lambda: self._pause_recording()))
            menu_items.append(item("Parar & Transcrever", lambda: self._stop_recording()))

        # Separator (represented as a blank line or disabled item, pystray handles lists directly)
        menu_items.append(pystray.Menu.SEPARATOR)

        # 3. Exit action
        menu_items.append(item("Sair", lambda: self._exit_app()))

        return pystray.Menu(*menu_items)

    def _restore_app(self) -> None:
        if self._on_restore_clicked:
            self._on_restore_clicked()

    def _pause_recording(self) -> None:
        if self._on_pause_clicked:
            self._on_pause_clicked()

    def _stop_recording(self) -> None:
        if self._on_stop_clicked:
            self._on_stop_clicked()

    def _exit_app(self) -> None:
        # Hide the tray icon immediately to feel responsive
        self.stop()
        if self._on_exit_clicked:
            self._on_exit_clicked()
