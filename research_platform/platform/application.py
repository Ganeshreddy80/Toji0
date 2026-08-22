"""TOJI Platform Application Wrapper.
"""

from __future__ import annotations

from research_platform.platform.startup import PlatformStartupCoordinator
from research_platform.platform.shutdown import PlatformShutdownCoordinator


class PlatformApplication:
    """The central unified runtime application managing startup and shutdown loops."""

    def __init__(self) -> None:
        self._startup = PlatformStartupCoordinator()
        self._shutdown = PlatformShutdownCoordinator()

    def boot(self) -> None:
        self._startup.boot_platform()

    def shutdown(self) -> None:
        self._shutdown.shutdown_platform()
        
        # Reset singleton state to ensure clean test isolation
        try:
            from research_platform.platform.state import PlatformState
            with PlatformState._lock:
                PlatformState._kernel = None
        except Exception:
            pass
