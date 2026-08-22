"""Domain events for the Monitoring Center.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class AlertTriggered(BaseEvent):
    """Fired when monitoring alerts fire."""
    pass
