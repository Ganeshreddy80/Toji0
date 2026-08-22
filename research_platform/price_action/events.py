"""Price action engine event definitions."""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class StructureDetected(BaseEvent):
    """Fired when a major swing point, BOS, or CHOCH is detected."""


@dataclass(frozen=True)
class ImbalanceDetected(BaseEvent):
    """Fired when a Fair Value Gap (FVG) or Volume Imbalance is formed."""


@dataclass(frozen=True)
class SessionUpdated(BaseEvent):
    """Fired when a new trading session (London, NY) starts/ends."""
