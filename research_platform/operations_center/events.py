"""Domain events for the Institutional Operations Center.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class OperationsDashboardRefreshed(BaseEvent):
    """Fired when the complete operations snapshot updates."""
    pass


@dataclass(frozen=True)
class OperationalAlertTriggered(BaseEvent):
    """Fired when a system warning or critical alert triggers."""
    pass
