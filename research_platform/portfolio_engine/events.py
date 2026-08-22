"""Event contracts for the Portfolio Construction & Risk Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PortfolioCreated(BaseEvent):
    """Fired when portfolio structure catalog registration completes."""
    pass


@dataclass(frozen=True)
class PortfolioUpdated(BaseEvent):
    """Fired when position weights shift."""
    pass


@dataclass(frozen=True)
class PortfolioOptimized(BaseEvent):
    """Fired when Mean-Variance or Black-Litterman optimization completes."""
    pass


@dataclass(frozen=True)
class AllocationCompleted(BaseEvent):
    """Fired when asset weight allocations finish."""
    pass


@dataclass(frozen=True)
class RiskCalculated(BaseEvent):
    """Fired when VaR, CVaR, or marginal risk budgets update."""
    pass


@dataclass(frozen=True)
class RebalanceTriggered(BaseEvent):
    """Fired when rebalancing threshold limits are crossed."""
    pass


@dataclass(frozen=True)
class RebalanceCompleted(BaseEvent):
    """Fired when portfolio rebalance trade plan completes."""
    pass


@dataclass(frozen=True)
class PortfolioPublished(BaseEvent):
    """Fired when approved weights publish to paper/live execution targets."""
    pass
