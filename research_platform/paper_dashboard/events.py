"""Domain events for the Institutional Paper Control Console.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ConsoleCommandExecuted(BaseEvent):
    """Fired when a CLI command is executed."""
    pass


@dataclass(frozen=True)
class PaperDashboardRefreshed(BaseEvent):
    """Fired when the paper dashboard updates its snapshot."""
    pass
