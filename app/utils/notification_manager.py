"""app.utils.notification_manager — Dispatcher for native OS desktop notifications.

Handles showing system notifications to alert the user about background recording and transcribing states.
"""

import subprocess
import shutil
import app.config as config


def send_notification(title: str, message: str) -> bool:
    """Send a native desktop notification to the user using notify-send on Linux.

    Returns:
        bool: True if successful, False otherwise.
    """
    if not config.PERSISTENT_NOTIFICATIONS_ENABLED:
        return False

    # Check if notify-send is available in the system path (typically /usr/bin/notify-send)
    notify_send_path = shutil.which("notify-send")
    if not notify_send_path:
        print("[NOTIFICATION MANAGER] notify-send not found on the system. Cannot trigger alert.")
        return False

    try:
        # Select icon based on content keywords
        icon_name = "audio-input-microphone"
        lower_title = title.lower()
        if "erro" in lower_title or "error" in lower_title or "falha" in lower_title:
            icon_name = "dialog-error"
        elif "concluído" in lower_title or "sucesso" in lower_title or "success" in lower_title:
            icon_name = "dialog-information"
        elif "transc" in lower_title:
            icon_name = "format-indent-more"

        subprocess.run(
            [
                notify_send_path,
                "-a", "Transcribe Assistant",
                "-i", icon_name,
                "-t", "6000",  # Expire time: 6 seconds
                title,
                message
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except Exception as e:
        print(f"[NOTIFICATION MANAGER] Failed to trigger notification: {e}")
        return False
