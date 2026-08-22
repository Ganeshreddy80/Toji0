"""Domain events for the Meta Portfolio Optimizer.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PortfolioOptimizationStarted(BaseEvent):
    """Fired when an optimization solver starts."""
    pass


@dataclass(frozen=True)
class PortfolioOptimized(BaseEvent):
    """Fired when weights are successfully computed."""
    pass


@dataclass(frozen=True)
class AllocationAdjusted(BaseEvent):
    """Fired when weights are set or updated."""
    pass


@dataclass(frozen=True)
class RiskBudgetBreached(BaseEvent):
    """Fired when a risk budget limit is violated."""
    pass


@dataclass(frozen=True)
class ExposureRebalanced(BaseEvent):
    """Fired when net or gross exposure is adjusted."""
    pass
