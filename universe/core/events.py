"""Universe-specific events for the TOJI Event Bus.

All events inherit from BaseEvent to integrate natively with the
existing InMemoryEventBus and downstream orchestrators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.core.types import Payload


@dataclass(frozen=True)
class AssetDiscovered(BaseEvent):
    """Fired when a new asset is discovered on an exchange."""


@dataclass(frozen=True)
class AssetPromoted(BaseEvent):
    """Fired when an asset moves to a higher tier."""


@dataclass(frozen=True)
class AssetDemoted(BaseEvent):
    """Fired when an asset moves to a lower tier."""


@dataclass(frozen=True)
class UniverseUpdated(BaseEvent):
    """Fired when a full scan cycle completes.

    Downstream consumers (e.g. future Price Action Engine) subscribe
    to this event to receive the latest ranked universe.
    """


@dataclass(frozen=True)
class WatchlistUpdated(BaseEvent):
    """Fired when a watchlist is created or modified."""
