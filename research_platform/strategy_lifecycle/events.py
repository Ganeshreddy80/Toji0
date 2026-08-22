"""Domain events for the Strategy Lifecycle Manager.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class StrategyCreated(BaseEvent):
    """Fired when a strategy is first initialized."""
    pass


@dataclass(frozen=True)
class StrategyUpdated(BaseEvent):
    """Fired when strategy state is updated."""
    pass


@dataclass(frozen=True)
class StrategyVersionCreated(BaseEvent):
    """Fired when a new version card is attached."""
    pass


@dataclass(frozen=True)
class StrategyApproved(BaseEvent):
    """Fired when a strategy approval gate passes."""
    pass


@dataclass(frozen=True)
class StrategyRejected(BaseEvent):
    """Fired when approval gate fails."""
    pass


@dataclass(frozen=True)
class StrategyPromoted(BaseEvent):
    """Fired when status transitions upward."""
    pass


@dataclass(frozen=True)
class StrategyRolledBack(BaseEvent):
    """Fired when rolled back to previous version."""
    pass


@dataclass(frozen=True)
class StrategyPaused(BaseEvent):
    """Fired when deployment halts execution."""
    pass


@dataclass(frozen=True)
class StrategyRetired(BaseEvent):
    """Fired when strategy transitions to RETIRED state."""
    pass


@dataclass(frozen=True)
class StrategyHealthChanged(BaseEvent):
    """Fired when strategy health diagnostic states modify."""
    pass


@dataclass(frozen=True)
class LifecycleSnapshotCreated(BaseEvent):
    """Fired when strategy portfolio states snapshot registers."""
    pass
