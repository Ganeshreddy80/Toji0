"""Thread-safe state store for the Position Sizing Engine subsystem."""

from __future__ import annotations

import collections
import threading
from datetime import datetime, timezone

from position_sizing.core.exceptions import StateStoreError
from position_sizing.core.interfaces import IPositionSizingStateStore
from position_sizing.core.models import PositionSizingState, PositionSizingSnapshot


class PositionSizingStateStore(IPositionSizingStateStore):
    """Thread-safe in-memory state store tracking position sizing snapshots."""

    def __init__(self, history_limit: int = 1000) -> None:
        self._history_limit = history_limit
        self._lock = threading.Lock()
        # Active snapshot mapping: symbol -> PositionSizingSnapshot
        self._snapshots: dict[str, PositionSizingSnapshot] = {}
        # Chronological history mapping: symbol -> deque[PositionSizingSnapshot]
        self._history: dict[str, collections.deque[PositionSizingSnapshot]] = {}

    def get_snapshot(self, symbol: str) -> PositionSizingSnapshot | None:
        """Retrieve the current position sizing snapshot for a symbol."""
        with self._lock:
            return self._snapshots.get(symbol)

    def update_snapshot(self, snapshot: PositionSizingSnapshot) -> None:
        """Update the active snapshot in a thread-safe manner."""
        if not snapshot.symbol:
            raise StateStoreError("Snapshot must have a valid symbol.")

        with self._lock:
            symbol = snapshot.symbol
            self._snapshots[symbol] = snapshot

            if symbol not in self._history:
                self._history[symbol] = collections.deque(maxlen=self._history_limit)

            self._history[symbol].append(snapshot)

    def get_history(self, symbol: str, limit: int = 100) -> list[PositionSizingSnapshot]:
        """Retrieve in-memory history of snapshots for a symbol sorted chronologically."""
        with self._lock:
            history_deque = self._history.get(symbol)
            if not history_deque:
                return []
            return list(history_deque)[-limit:]

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: PositionSizingState
    ) -> PositionSizingSnapshot:
        """Safely apply a timeframe update to the active snapshot."""
        with self._lock:
            current = self._snapshots.get(symbol)
            if not current:
                raise StateStoreError(
                    f"No active snapshot found for symbol '{symbol}' to update."
                )

            updated_states = dict(current.states)
            updated_states[timeframe] = state_update

            updated_snapshot = current.model_copy(
                update={
                    "states": updated_states,
                    "timestamp": state_update.updated_at,
                }
            )

            self._snapshots[symbol] = updated_snapshot
            if symbol not in self._history:
                self._history[symbol] = collections.deque(maxlen=self._history_limit)
            self._history[symbol].append(updated_snapshot)
            return updated_snapshot

    def clear(self) -> None:
        """Purge all tracked states from memory."""
        with self._lock:
            self._snapshots.clear()
            self._history.clear()
