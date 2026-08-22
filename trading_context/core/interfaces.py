"""Interfaces for the Trading Context subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from trading_context.core.models import TradingContextSnapshot, TradingContext


@runtime_checkable
class ITradingContextStateStore(Protocol):
    """Protocol for thread-safe in-memory storage of active Trading Context snapshots."""

    def update_snapshot(self, snapshot: TradingContextSnapshot) -> None:
        """Overwrite or store a new trading context snapshot."""
        ...

    def get_snapshot(self, symbol: str) -> TradingContextSnapshot | None:
        """Fetch the current trading context snapshot for a symbol."""
        ...

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: TradingContext
    ) -> TradingContextSnapshot:
        """Add or update a single timeframe state inside the symbol's snapshot."""
        ...

    def clear(self) -> None:
        """Clear all stored state."""
        ...


@runtime_checkable
class ITradingContextRepository(Protocol):
    """Protocol for trading context snapshot persistence."""

    def save_snapshot(self, snapshot: TradingContextSnapshot) -> None:
        """Persist a trading context snapshot."""
        ...

    def load_snapshot(self, snapshot_id: str) -> TradingContextSnapshot | None:
        """Retrieve a specific snapshot by ID."""
        ...

    def load_latest_snapshot(self, symbol: str) -> TradingContextSnapshot | None:
        """Retrieve the latest snapshot for a symbol."""
        ...

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[TradingContextSnapshot]:
        """Retrieve historical snapshots over a timeframe range."""
        ...
