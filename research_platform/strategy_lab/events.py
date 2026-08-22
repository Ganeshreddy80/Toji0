"""Event contracts for the Strategy Lab.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class StrategyCreated(BaseEvent):
    """Fired when a new StrategyDefinition is created."""
    pass


@dataclass(frozen=True)
class StrategyUpdated(BaseEvent):
    """Fired when a StrategyDefinition is modified."""
    pass


@dataclass(frozen=True)
class StrategyValidated(BaseEvent):
    """Fired when strategy configuration succeeds structural validation checks."""
    pass


@dataclass(frozen=True)
class StrategyRejected(BaseEvent):
    """Fired when strategy violates risk limits or validation constraints."""
    pass


@dataclass(frozen=True)
class StrategyApproved(BaseEvent):
    """Fired when strategy gets approved for backtest execution."""
    pass


@dataclass(frozen=True)
class StrategyArchived(BaseEvent):
    """Fired when strategy is retired and archived."""
    pass


@dataclass(frozen=True)
class StrategyVersionCreated(BaseEvent):
    """Fired when a new version code is registered."""
    pass


@dataclass(frozen=True)
class StrategyExported(BaseEvent):
    """Fired when strategy definition is exported to the Backtesting Engine."""
    pass
