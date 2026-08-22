"""Domain events for the Strategy Registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class StrategyRegistered(BaseEvent):
    """Fired when a strategy is first registered."""
    pass


@dataclass(frozen=True)
class StrategyRegistrySnapshotCreated(BaseEvent):
    """Fired when a registry snapshot is created."""
    pass
