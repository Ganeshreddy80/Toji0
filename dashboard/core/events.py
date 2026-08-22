"""System events for the Dashboard Platform subsystem.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class DashboardInitialized(BaseEvent):
    """Fired when the Dashboard Platform plugin starts successfully."""


@dataclass(frozen=True)
class DashboardShutdown(BaseEvent):
    """Fired when the Dashboard Platform plugin shuts down."""
