"""Thread-safe state store for the Price Action Subsystem."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import threading
from typing import Any

from price_action.core.enums import PatternStatus, PatternType
from price_action.core.exceptions import StateStoreError
from price_action.core.interfaces import IPatternStateStore
from price_action.core.models import (
    PatternMatch,
    PatternSnapshot,
    PatternState,
)


class PriceActionStateStore(IPatternStateStore):
    """Thread-safe, replay-safe in-memory state store tracking price action pattern states."""

    def __init__(self, history_limit: int = 1000) -> None:
        self._history_limit = history_limit
        self._lock = threading.Lock()
        # Active snapshot mapping: symbol -> PatternSnapshot
        self._snapshots: dict[str, PatternSnapshot] = {}
        # Chronological history mapping: symbol -> deque[PatternSnapshot]
        self._history: dict[str, collections.deque[PatternSnapshot]] = {}

    def get_snapshot(self, symbol: str) -> PatternSnapshot | None:
        """Retrieve the current state snapshot for a symbol."""
        with self._lock:
            return self._snapshots.get(symbol)

    def update_snapshot(self, snapshot: PatternSnapshot) -> None:
        """Update the active state snapshot in a thread-safe manner."""
        if not snapshot.symbol:
            raise StateStoreError("Snapshot must have a valid symbol.")

        with self._lock:
            symbol = snapshot.symbol
            self._snapshots[symbol] = snapshot

            if symbol not in self._history:
                self._history[symbol] = collections.deque(maxlen=self._history_limit)

            self._history[symbol].append(snapshot)

    def get_history(self, symbol: str, limit: int = 100) -> list[PatternSnapshot]:
        """Retrieve in-memory history of snapshots for a symbol sorted chronologically."""
        with self._lock:
            history_deque = self._history.get(symbol)
            if not history_deque:
                return []
            return list(history_deque)[-limit:]

    def update_timeframe_state(
        self, symbol: str, timeframe: str, state_update: PatternState
    ) -> PatternSnapshot:
        """Safely apply a timeframe update to the active snapshot."""
        with self._lock:
            current = self._snapshots.get(symbol)
            if not current:
                import uuid
                current = PatternSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=state_update.updated_at,
                    states={},
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

    def query(
        self,
        symbol: str,
        pattern_type: PatternType | None = None,
        status: PatternStatus | None = None,
    ) -> list[PatternMatch]:
        """Query currently tracked pattern matches."""
        with self._lock:
            snapshot = self._snapshots.get(symbol)
            if not snapshot:
                return []

            results = []
            for state in snapshot.states.values():
                # Combine active and historical matches
                matches = state.active_patterns + state.historical_patterns
                for match in matches:
                    if pattern_type is not None and match.pattern_type != pattern_type:
                        continue
                    if status is not None and match.status != status:
                        continue
                    results.append(match)
            return results

    def clear(self) -> None:
        """Purge all tracked states from memory."""
        with self._lock:
            self._snapshots.clear()
            self._history.clear()
