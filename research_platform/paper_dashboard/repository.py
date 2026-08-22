"""Thread-safe memory repository caching console logs.
"""

from __future__ import annotations

import threading
from typing import List, Optional
from research_platform.paper_dashboard.interfaces import IPaperDashboardRepository
from research_platform.paper_dashboard.models import (
    ConsoleCommand,
    ConsoleSessionSummary,
)


class PaperDashboardRepository(IPaperDashboardRepository):
    """Memory-backed store caching active dashboard snapshots."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._commands: List[ConsoleCommand] = []
        self._summary: Optional[ConsoleSessionSummary] = None

    def save_command(self, command: ConsoleCommand) -> None:
        with self._lock:
            self._commands.append(command)

    def list_commands(self) -> List[ConsoleCommand]:
        with self._lock:
            return list(self._commands)

    def save_summary(self, summary: ConsoleSessionSummary) -> None:
        with self._lock:
            self._summary = summary

    def get_latest_summary(self) -> Optional[ConsoleSessionSummary]:
        with self._lock:
            return self._summary
