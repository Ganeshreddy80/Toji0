"""Abstract contracts for the Institutional Dashboard & Paper Control Console.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.paper_dashboard.models import (
    ConsoleCommand,
    ConsoleSessionSummary,
    ConsoleState,
)


class IConsoleController(abc.ABC):
    """Abstract contract for parsing and executing CLI command texts."""

    @abc.abstractmethod
    def execute_command_text(self, cmd_text: str) -> str:
        """Parse string commands and execute actions."""


class IPaperDashboardRepository(abc.ABC):
    """Abstract contract for storing control commands logs and states."""

    @abc.abstractmethod
    def save_command(self, command: ConsoleCommand) -> None:
        """Persist console command logs."""

    @abc.abstractmethod
    def list_commands(self) -> List[ConsoleCommand]:
        """List all executed commands."""

    @abc.abstractmethod
    def save_summary(self, summary: ConsoleSessionSummary) -> None:
        """Persist the latest dashboard metrics summary."""

    @abc.abstractmethod
    def get_latest_summary(self) -> Optional[ConsoleSessionSummary]:
        """Retrieve the latest cached metrics summary."""


class IPaperDashboardOrchestrator(abc.ABC):
    """Abstract contract for paper control console orchestration."""

    @abc.abstractmethod
    def refresh_dashboard(self) -> ConsoleSessionSummary:
        """Fetch current accounts, exposures, drawdowns and router modes."""
