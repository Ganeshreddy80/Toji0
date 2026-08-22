"""Event contracts for the Optimization Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class OptimizationStarted(BaseEvent):
    """Fired when strategy optimization parameter search is initialized."""
    pass


@dataclass(frozen=True)
class OptimizationCompleted(BaseEvent):
    """Fired when full parameter sweeps finalize."""
    pass


@dataclass(frozen=True)
class TrialEvaluated(BaseEvent):
    """Fired when a single parameter configuration trial completes backtesting."""
    pass


@dataclass(frozen=True)
class ParetoFrontUpdated(BaseEvent):
    """Fired when multi-objective Pareto-front solutions are re-sorted."""
    pass


@dataclass(frozen=True)
class WalkForwardCompleted(BaseEvent):
    """Fired when rolling walk-forward window testing completes."""
    pass
