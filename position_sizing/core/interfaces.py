"""Interfaces and protocols for the Position Sizing Engine subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from trading_context.core.models import TradingContext
from risk_engine.core.models import RiskAssessment
from position_sizing.core.models import (
    PositionSizingResult,
    PositionSizingState,
    PositionSizingSnapshot,
)


class IPositionSizingEngine(Protocol):
    """Protocol for executing position sizing calculations."""

    def calculate_size(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> PositionSizingResult:
        """Run calculators and validations to determine final size."""
        ...


class IPositionSizingRepository(Protocol):
    """Protocol for persistent storage and retrieval of PositionSizing snapshots."""

    def save_snapshot(self, snapshot: PositionSizingSnapshot) -> None:
        """Persist a position sizing snapshot."""
        ...

    def load_snapshot(self, snapshot_id: str) -> PositionSizingSnapshot | None:
        """Load a snapshot by its unique ID."""
        ...

    def load_latest_snapshot(self, symbol: str) -> PositionSizingSnapshot | None:
        """Load the most recent snapshot for a symbol."""
        ...

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[PositionSizingSnapshot]:
        """Query historical snapshots over a time range."""
        ...


class IPositionSizingStateStore(Protocol):
    """Protocol for thread-safe in-memory state tracking."""

    def get_snapshot(self, symbol: str) -> PositionSizingSnapshot | None:
        """Retrieve active snapshot for a symbol."""
        ...

    def update_snapshot(self, snapshot: PositionSizingSnapshot) -> None:
        """Update active snapshot."""
        ...

    def get_history(self, symbol: str, limit: int = 100) -> list[PositionSizingSnapshot]:
        """Retrieve list of historical snapshots in memory."""
        ...

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: PositionSizingState
    ) -> PositionSizingSnapshot:
        """Update timeframe-specific state."""
        ...

    def clear(self) -> None:
        """Purge all active tracked states."""
        ...


class ISizingCalculator(Protocol):
    """Protocol for individual position sizing algorithms."""

    def calculate(
        self,
        context: TradingContext,
        risk_assessment: RiskAssessment,
        **kwargs: Any,
    ) -> tuple[float, list[str]]:
        """Calculate quantity. Returns tuple of (quantity, reasons)."""
        ...
