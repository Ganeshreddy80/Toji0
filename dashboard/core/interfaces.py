"""Interfaces and protocols for the Dashboard Platform subsystem."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from dashboard.core.models import DashboardSnapshot


class IDashboardStateStore(Protocol):
    """Protocol for the thread-safe active state store of dashboard snapshots."""

    def get_snapshot(self, symbol: str, timeframe: str) -> DashboardSnapshot | None:
        """Retrieve the active dashboard snapshot for a symbol and timeframe."""
        ...

    def update_snapshot(self, snapshot: DashboardSnapshot) -> None:
        """Update the active dashboard snapshot."""
        ...

    def get_all_snapshots(self) -> list[DashboardSnapshot]:
        """Retrieve all active dashboard snapshots."""
        ...

    def clear(self) -> None:
        """Purge all tracked states from memory."""
        ...


class IDashboardRepository(Protocol):
    """Protocol for persistent storage and retrieval of Dashboard snapshots."""

    def save_snapshot(self, snapshot: DashboardSnapshot) -> None:
        """Persist a dashboard snapshot."""
        ...

    def load_snapshot(self, snapshot_id: str) -> DashboardSnapshot | None:
        """Load a specific dashboard snapshot by its ID."""
        ...

    def load_latest_snapshot(self, symbol: str, timeframe: str) -> DashboardSnapshot | None:
        """Load the most recent dashboard snapshot for a symbol and timeframe."""
        ...

    def get_historical_snapshots(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[DashboardSnapshot]:
        """Load historical dashboard snapshots over a time window."""
        ...
