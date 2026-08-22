"""Domain events for TOJI Operating System.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class KernelBooted(BaseEvent):
    """Fired when OS kernel completes bootstrap initialization."""
    pass


@dataclass(frozen=True)
class KernelShutdown(BaseEvent):
    """Fired when OS kernel completes shutdown sequence."""
    pass
