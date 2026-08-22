"""Domain events for the Alpha Factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class SignalGenerated(BaseEvent):
    """Fired when alpha signal emits."""
    pass


@dataclass(frozen=True)
class ComboCreated(BaseEvent):
    """Fired when alpha combinations compile."""
    pass


@dataclass(frozen=True)
class EnsembleModelUpdated(BaseEvent):
    """Fired when ensemble parameters modify."""
    pass
