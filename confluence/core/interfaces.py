"""Interfaces for the Confluence Engine."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from market_intelligence.core.models import MarketState
from price_action.core.models import PatternState
from confluence.core.models import ConfluenceSnapshot, ConfluenceState, ConfluenceScore


@runtime_checkable
class IConfluenceStateStore(Protocol):
    """Protocol for in-memory thread-safe state storage of confluence snapshots."""

    def update_snapshot(self, snapshot: ConfluenceSnapshot) -> None:
        """Overwrite or store a new confluence snapshot."""
        ...

    def get_snapshot(self, symbol: str) -> ConfluenceSnapshot | None:
        """Fetch the current snapshot for a symbol."""
        ...

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: ConfluenceState
    ) -> ConfluenceSnapshot:
        """Add or update a single timeframe's state inside the symbol's snapshot."""
        ...

    def clear(self) -> None:
        """Clear all stored state."""
        ...


@runtime_checkable
class IConfluenceRepository(Protocol):
    """Protocol for snapshot and score persistence."""

    def save_snapshot(self, snapshot: ConfluenceSnapshot) -> None:
        """Persist a confluence snapshot."""
        ...

    def load_snapshot(self, snapshot_id: str) -> ConfluenceSnapshot | None:
        """Retrieve a specific snapshot by ID."""
        ...

    def load_latest_snapshot(self, symbol: str) -> ConfluenceSnapshot | None:
        """Retrieve the latest snapshot for a symbol."""
        ...

    def get_historical_snapshots(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[ConfluenceSnapshot]:
        """Retrieve historical snapshots over a timeframe range."""
        ...


@runtime_checkable
class IConfluenceEngine(Protocol):
    """Protocol for calculating confluence setup scores."""

    def evaluate(self, market_state: MarketState, pattern_state: PatternState | None) -> ConfluenceScore:
        """Calculate overall confluence score and factors from market and pattern states."""
        ...
