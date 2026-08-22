"""Domain events for Portfolio Construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class AllocationRebalanced(BaseEvent):
    """Fired when portfolio constructs new allocation target weights."""
    pass
