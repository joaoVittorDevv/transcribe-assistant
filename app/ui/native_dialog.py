"""app.ui.native_dialog — Native file dialog with Zenity fallback.

On Linux, uses Zenity (GTK file chooser) for a native GNOME experience
with sidebar navigation, thumbnails, and breadcrumbs. Falls back to
tkinter.filedialog on Windows, macOS, or if Zenity is not installed.

Usage:
    path = open_audio_file(
        title="Select audio",
        extensions={".mp3", ".wav", ".ogg"},
    )
    if path:
        process(path)
"""

import subprocess
import sys
from pathlib import Path
from tkinter import filedialog


def open_audio_file(
    title: str,
    extensions: set[str],
    filetypes_label: str = "Audio files",
) -> str | None:
    """Open a file selection dialog and return the chosen file path.

    On Linux, attempts to use Zenity for a native GTK dialog.
    Falls back to tkinter.filedialog on other OSes or if Zenity fails.

    Args:
        title:           Dialog window title.
        extensions:      Set of accepted file extensions (e.g. {".mp3", ".wav"}).
        filetypes_label: Label shown in the file type filter dropdown.

    Returns:
        Absolute file path as string, or None if the user cancelled.
    """
    if sys.platform == "linux":
        result = _try_zenity(title, extensions, filetypes_label)
        if result is not None:
            return result  # "" means Zenity ran but user cancelled → return None below
        # Zenity not available — fall through to tkinter

    return _tk_dialog(title, extensions, filetypes_label)


def _try_zenity(
    title: str,
    extensions: set[str],
    filetypes_label: str,
) -> str | None:
    """Attempt to open a Zenity file selection dialog.

    Returns:
        - file path string if user selected a file
        - None if Zenity is not installed (caller should fall through)

    When the user cancels, returns "" which the caller converts to None.
    """
    # Build filter: "Audio files | *.mp3 *.wav *.ogg"
    patterns = " ".join(f"*{ext}" for ext in sorted(extensions))
    file_filter = f"{filetypes_label} | {patterns}"

    cmd = [
        "zenity",
        "--file-selection",
        f"--title={title}",
        f"--file-filter={file_filter}",
        "--file-filter=All files | *",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min max — user might take time browsing
        )
    except FileNotFoundError:
        # Zenity not installed
        return None
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()

    # returncode 1 = user cancelled, or empty output
    return ""


def _tk_dialog(
    title: str,
    extensions: set[str],
    filetypes_label: str,
) -> str | None:
    """Fallback: open a tkinter file dialog (native on Windows/macOS)."""
    patterns = " ".join(f"*{ext}" for ext in sorted(extensions))
    filetypes = [
        (filetypes_label, patterns),
        ("All files", "*.*"),
    ]

    file_path = filedialog.askopenfilename(
        title=title,
        filetypes=filetypes,
        initialdir=str(Path.home()),
    )

    return file_path if file_path else None
