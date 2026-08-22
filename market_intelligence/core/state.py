"""Thread-safe state store for the Market Intelligence Layer."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import threading
from typing import Any

from market_intelligence.core.exceptions import StateStoreError
from market_intelligence.core.interfaces import IStateStore
from market_intelligence.core.models import MarketSnapshot


class MarketIntelligenceState(IStateStore):
    """Thread-safe, replay-safe in-memory state tracking store.

    Maintains active snapshots and chronological rolling history per symbol.
    """

    def __init__(self, history_limit: int = 1000) -> None:
        self._history_limit = history_limit
        # Locks state mutations
        self._lock = threading.Lock()
        # Active snapshot mapping: symbol -> MarketSnapshot
        self._snapshots: dict[str, MarketSnapshot] = {}
        # Chronological history mapping: symbol -> deque[MarketSnapshot]
        self._history: dict[str, collections.deque[MarketSnapshot]] = {}

    def get_snapshot(self, symbol: str) -> MarketSnapshot | None:
        """Retrieve the current state snapshot for a symbol.

        Thread-safe read accessor.
        """
        with self._lock:
            return self._snapshots.get(symbol)

    def update_snapshot(self, snapshot: MarketSnapshot) -> None:
        """Update the active state snapshot in a thread-safe manner.

        Appends the new snapshot to the history ring buffer.
        """
        if not snapshot.symbol:
            raise StateStoreError("Snapshot must have a valid symbol.")

        with self._lock:
            symbol = snapshot.symbol
            self._snapshots[symbol] = snapshot

            if symbol not in self._history:
                self._history[symbol] = collections.deque(maxlen=self._history_limit)

            self._history[symbol].append(snapshot)

    def get_history(self, symbol: str, limit: int = 100) -> list[MarketSnapshot]:
        """Retrieve in-memory history of snapshots for a symbol.

        Sorted chronologically.
        """
        with self._lock:
            history_deque = self._history.get(symbol)
            if not history_deque:
                return []
            # Return list of recent snapshots up to limit
            return list(history_deque)[-limit:]

    def clear(self) -> None:
        """Purge all tracked states from memory."""
        with self._lock:
            self._snapshots.clear()
            self._history.clear()

    # Helper for incremental timeframe state updates
    def update_timeframe_state(self, symbol: str, timeframe: str, state_update: Any) -> MarketSnapshot:
        """Safely apply an incremental timeframe update to the active snapshot.

        If no active snapshot exists, raises StateStoreError.
        """
        with self._lock:
            current = self._snapshots.get(symbol)
            if not current:
                raise StateStoreError(
                    f"No active snapshot found for symbol '{symbol}' to incrementally update."
                )

            # Copy and update timeframe state map
            updated_states = dict(current.states)
            updated_states[timeframe] = state_update

            # Dynamically extract updated timestamp
            new_timestamp = datetime.now(timezone.utc)
            for attr in ("timestamp", "updated_at", "end_time", "generated_at"):
                if hasattr(state_update, attr):
                    new_timestamp = getattr(state_update, attr)
                    break

            updated_snapshot = current.model_copy(
                update={
                    "states": updated_states,
                    "timestamp": new_timestamp,
                }
            )

            self._snapshots[symbol] = updated_snapshot
            self._history[symbol].append(updated_snapshot)
            return updated_snapshot

