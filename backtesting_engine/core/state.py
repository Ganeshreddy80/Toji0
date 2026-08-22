"""Thread-safe state store for active backtest replay sessions (Sprint 7A)."""

from __future__ import annotations

import collections
import threading
from typing import Dict, List, Optional

from backtesting_engine.core.exceptions import BacktestOrchestratorError
from backtesting_engine.core.models import BacktestResult


class BacktestStateStore:
    """Thread-safe, replay-safe state store tracking active backtest results.

    State Ownership Specification:
    - Purpose: Track transient runtime execution state for active in-flight backtests across threads.
    - Lifetime: Transient in-memory state during runtime execution lifecycle.
    - Ownership: Owns active backtest runtime states. Historical long-term persistence is owned exclusively by BacktestRepository.
    """

    def __init__(self, history_limit: int = 1000) -> None:
        self._history_limit = history_limit
        self._lock = threading.RLock()
        self._results: Dict[str, BacktestResult] = {}
        self._history: collections.deque[BacktestResult] = collections.deque(maxlen=history_limit)

    def get_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """Retrieve a backtest result by ID."""
        with self._lock:
            return self._results.get(backtest_id)

    def save_result(self, result: BacktestResult) -> None:
        """Update or insert a backtest result thread-safely."""
        if not result or not result.backtest_id:
            raise BacktestOrchestratorError("BacktestResult must contain a valid backtest_id.")

        with self._lock:
            bt_id = result.backtest_id
            self._results[bt_id] = result
            self._history.append(result)

    def list_results(self, limit: int = 100) -> List[BacktestResult]:
        """Retrieve in-memory history of backtest results."""
        with self._lock:
            return list(self._history)[-limit:]

    def clear(self) -> None:
        """Purge tracked states from memory."""
        with self._lock:
            self._results.clear()
            self._history.clear()
