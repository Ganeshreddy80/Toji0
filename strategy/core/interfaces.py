"""Interfaces for the Strategy Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyType
from strategy.core.models import StrategySnapshot, StrategyState, StrategySignal


@runtime_checkable
class IStrategyStateStore(Protocol):
    """Protocol for in-memory thread-safe state storage of strategy snapshots."""

    def update_snapshot(self, snapshot: StrategySnapshot) -> None:
        """Overwrite or store a new strategy snapshot."""
        ...

    def get_snapshot(self, symbol: str) -> StrategySnapshot | None:
        """Fetch the current strategy snapshot for a symbol."""
        ...

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: StrategyState
    ) -> StrategySnapshot:
        """Add or update a single timeframe's state inside the symbol's snapshot."""
        ...

    def clear(self) -> None:
        """Clear all stored state."""
        ...


@runtime_checkable
class IStrategyRepository(Protocol):
    """Protocol for strategy snapshot and signal persistence."""

    def save_snapshot(self, snapshot: StrategySnapshot) -> None:
        """Persist a strategy snapshot."""
        ...

    def load_snapshot(self, snapshot_id: str) -> StrategySnapshot | None:
        """Retrieve a specific snapshot by ID."""
        ...

    def load_latest_snapshot(self, symbol: str) -> StrategySnapshot | None:
        """Retrieve the latest snapshot for a symbol."""
        ...

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[StrategySnapshot]:
        """Retrieve historical snapshots over a timeframe range."""
        ...


@runtime_checkable
class ISignalScorer(Protocol):
    """Protocol for scoring and ranking candidate strategy setup signals."""

    def score_signal(
        self,
        signal: StrategySignal,
        market_state: MarketState,
        confluence_state: ConfluenceState | None = None,
    ) -> float:
        """Calculate composite rank score for a candidate signal."""
        ...


@runtime_checkable
class IStrategy(Protocol):
    """Protocol for an individual institutional strategy rule module."""

    @property
    def strategy_type(self) -> StrategyType:
        """Category / type of strategy."""
        ...

    @property
    def name(self) -> str:
        """Human-readable strategy identifier."""
        ...

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal | None:
        """Evaluate strategy rules against current market context."""
        ...


@runtime_checkable
class IStrategyRegistry(Protocol):
    """Protocol for dynamic, thread-safe strategy registration and management."""

    def register_strategy(self, strategy: IStrategy) -> None:
        """Register a strategy implementation."""
        ...

    def unregister_strategy(self, strategy_type: StrategyType) -> None:
        """Unregister a strategy by type."""
        ...

    def get_strategy(self, strategy_type: StrategyType) -> IStrategy | None:
        """Retrieve registered strategy instance."""
        ...

    def list_strategies(self) -> list[IStrategy]:
        """List all registered strategy instances."""
        ...

    def set_strategy_enabled(self, strategy_type: StrategyType, enabled: bool) -> None:
        """Enable or disable a specific strategy type."""
        ...

    def is_strategy_enabled(self, strategy_type: StrategyType) -> bool:
        """Check if a strategy type is currently enabled."""
        ...

    def evaluate_all(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
        min_confidence: float = 0.0,
    ) -> list[StrategySignal]:
        """Evaluate all active strategies and return valid non-WAIT signals."""
        ...


@runtime_checkable
class IStrategyEngine(Protocol):
    """Protocol for calculating/evaluating strategy setup decisions."""

    def evaluate(
        self,
        market_state: MarketState,
        pattern_state: PatternState | None,
        confluence_state: ConfluenceState | None,
    ) -> StrategySignal:
        """Evaluate strategy signals from current market, pattern, and confluence states."""
        ...

