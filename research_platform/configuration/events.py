"""Domain events for the Configuration Manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ConfigurationUpdated(BaseEvent):
    """Fired when configuration parameters are updated."""
    pass


@dataclass(frozen=True)
class ConfigurationReloaded(BaseEvent):
    """Fired when hot reloads successfully trigger."""
    pass
