"""Event contracts for the Institutional Memory Platform.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class MemoryPersisted(BaseEvent):
    """Fired when an append-only historical memory is saved."""
    pass


@dataclass(frozen=True)
class ReplayStarted(BaseEvent):
    """Fired when state replay reconstruction begins."""
    pass


@dataclass(frozen=True)
class ReplayCompleted(BaseEvent):
    """Fired when state replay context finishes compiling."""
    pass


@dataclass(frozen=True)
class RelationshipLinked(BaseEvent):
    """Fired when lineage links are created."""
    pass


@dataclass(frozen=True)
class LessonLearned(BaseEvent):
    """Fired when session observations generate lessons."""
    pass


@dataclass(frozen=True)
class LessonValidated(BaseEvent):
    """Fired when backtesting research confirms lesson viability."""
    pass
