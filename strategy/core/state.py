"""Thread-safe state store for the Strategy Engine."""

from __future__ import annotations

import collections
import threading
from datetime import datetime, timezone

from strategy.core.exceptions import StateStoreError
from strategy.core.interfaces import IStrategyStateStore
from strategy.core.models import (
    StrategySnapshot,
    StrategyState,
)


class StrategyStateStore(IStrategyStateStore):
    """Thread-safe, replay-safe in-memory state store tracking strategy snapshot states."""

    def __init__(self, history_limit: int = 1000) -> None:
        self._history_limit = history_limit
        self._lock = threading.Lock()
        # Active snapshot mapping: symbol -> StrategySnapshot
        self._snapshots: dict[str, StrategySnapshot] = {}
        # Chronological history mapping: symbol -> deque[StrategySnapshot]
        self._history: dict[str, collections.deque[StrategySnapshot]] = {}

    def get_snapshot(self, symbol: str) -> StrategySnapshot | None:
        """Retrieve the current strategy snapshot for a symbol."""
        with self._lock:
            return self._snapshots.get(symbol)

    def update_snapshot(self, snapshot: StrategySnapshot) -> None:
        """Update the active strategy snapshot in a thread-safe manner."""
        if not snapshot.symbol:
            raise StateStoreError("Snapshot must have a valid symbol.")

        with self._lock:
            symbol = snapshot.symbol
            self._snapshots[symbol] = snapshot

            if symbol not in self._history:
                self._history[symbol] = collections.deque(maxlen=self._history_limit)

            self._history[symbol].append(snapshot)

    def get_history(self, symbol: str, limit: int = 100) -> list[StrategySnapshot]:
        """Retrieve in-memory history of snapshots for a symbol sorted chronologically."""
        with self._lock:
            history_deque = self._history.get(symbol)
            if not history_deque:
                return []
            return list(history_deque)[-limit:]

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: StrategyState
    ) -> StrategySnapshot:
        """Safely apply a timeframe update to the active strategy snapshot."""
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
            
