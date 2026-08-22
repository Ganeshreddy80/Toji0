"""Domain events for the Institutional Paper Trading Foundation.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PaperSessionStarted(BaseEvent):
    """Fired when a paper session starts."""
    pass


@dataclass(frozen=True)
class PaperOrderSubmitted(BaseEvent):
    """Fired when a paper order is submitted."""
    pass


@dataclass(frozen=True)
class PaperOrderFilled(BaseEvent):
    """Fired when a paper order fills on exchange."""
    pass


@dataclass(frozen=True)
class PaperOrderMatched(BaseEvent):
    """Fired when a paper order fills on exchange (compatibility alias)."""
    pass


@dataclass(frozen=True)
class PaperOrderCancelled(BaseEvent):
    """Fired when a paper order is cancelled."""
    pass


@dataclass(frozen=True)
class PaperSessionStopped(BaseEvent):
    """Fired when a paper session stops."""
    pass
