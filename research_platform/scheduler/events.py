"""Domain events for the Strategy Scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class JobScheduled(BaseEvent):
    """Fired when a new execution job is queued."""
    pass


@dataclass(frozen=True)
class JobStarted(BaseEvent):
    """Fired when job execution begins."""
    pass


@dataclass(frozen=True)
class JobCompleted(BaseEvent):
    """Fired when job completes successfully."""
    pass


@dataclass(frozen=True)
class JobFailed(BaseEvent):
    """Fired when execution encounters error."""
    pass


@dataclass(frozen=True)
class JobCanceled(BaseEvent):
    """Fired when execution is canceled."""
    pass
