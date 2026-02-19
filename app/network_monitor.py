"""app.network_monitor — Background connectivity checker.

Runs a daemon thread that periodically attempts a TCP connection to a
reliable host (default: Google DNS 8.8.8.8:53) to determine if the
machine has internet access.

Usage:
    monitor = NetworkMonitor(on_status_change=my_callback)
    monitor.start()
    # ... app runs ...
    print(monitor.is_online)
    monitor.stop()
"""

import socket
import threading
import time
from typing import Callable

from app.config import (
    NETWORK_CHECK_INTERVAL,
    NETWORK_PING_HOST,
    NETWORK_PING_PORT,
)

_TIMEOUT_SECONDS = 3


class NetworkMonitor:
    """Periodically checks internet connectivity in a background thread.

    Args:
        on_status_change: Optional callback invoked whenever the online
                          status changes. Receives a single bool argument.
    """

    def __init__(
        self,
        on_status_change: Callable[[bool], None] | None = None,
    ) -> None:
        self._on_status_change = on_status_change
        self._is_online: bool = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_online(self) -> bool:
        """Current connectivity status (updated every NETWORK_CHECK_INTERVAL s)."""
        return self._is_online

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="NetworkMonitor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the monitoring thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=_TIMEOUT_SECONDS + 1)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_connection(self) -> bool:
        """Return True if a TCP connection to the ping host succeeds."""
        try:
            with socket.create_connection(
                (NETWORK_PING_HOST, NETWORK_PING_PORT),
                timeout=_TIMEOUT_SECONDS,
            ):
                return True
        except OSError:
            return False

    def _monitor_loop(self) -> None:
        """Main loop: check connection, notify on change, sleep, repeat."""
        # Immediate first check
        self._update_status(self._check_connection())

        while not self._stop_event.wait(timeout=NETWORK_CHECK_INTERVAL):
            self._update_status(self._check_connection())

    def _update_status(self, new_status: bool) -> None:
        """Update internal state and notify callback if status changed."""
        if new_status != self._is_online:
            self._is_online = new_status
            if self._on_status_change:
                self._on_status_change(new_status)
