"""Persistence repository for the Backtesting Engine (Sprint 7A)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, List, Optional

from backtesting_engine.core.exceptions import BacktestRepositoryError
from backtesting_engine.core.interfaces import IBacktestRepository
from backtesting_engine.core.models import BacktestResult

logger = logging.getLogger(__name__)


class BacktestRepository(IBacktestRepository):
    """Thread-safe, atomic persistence repository for backtest configurations, trades, and results."""

    def __init__(self, storage_engine: Any | None = None) -> None:
        self._storage = storage_engine
        self._by_id: dict[str, BacktestResult] = {}
        self._history: list[BacktestResult] = []
        self._lock = threading.RLock()

    def save_result(self, result: BacktestResult) -> None:
        """Persist a backtest result atomically using Option A pattern.

        Concurrency Invariant:
        All persistence calls acquire self._lock to ensure that durable storage writes
        and in-memory repository cache updates are atomic, thread-safe, and strictly ordered.
        If storage persistence fails, the in-memory cache is never modified, ensuring zero divergence.
        """
        if not result or not result.backtest_id:
            raise BacktestRepositoryError("BacktestResult must contain a valid backtest_id.")

        with self._lock:
            # 1. Option A: Persist to storage engine first (durable phase)
            if self._storage:
                try:
                    row = {
                        "backtest_id": result.backtest_id,
                        "name": result.config.name,
                        "status": result.status.value,
                        "completed_at": result.completed_at.isoformat(),
                        "final_equity": result.final_equity,
                        "data": result.model_dump_json(),
                    }
                    self._storage.write_rows("backtest_results", [row])
                except Exception as e:
                    logger.error("BacktestRepository: Failed to write backtest result row: %s", e)
                    raise BacktestRepositoryError(f"Failed to persist backtest result to storage: {e}") from e

            # 2. Commit to memory cache only after successful storage write
            bt_id = result.backtest_id
            self._by_id[bt_id] = result
            self._history.append(result)

            # Bounded memory cache eviction
            if len(self._history) > 1000:
                removed = self._history.pop(0)
                if not any(item.backtest_id == removed.backtest_id for item in self._history):
                    self._by_id.pop(removed.backtest_id, None)

    def load_result(self, backtest_id: str) -> Optional[BacktestResult]:
        """Load a backtest result by ID."""
        with self._lock:
            if backtest_id in self._by_id:
                return self._by_id[backtest_id]

        if self._storage:
            try:
                query = "SELECT data FROM backtest_results WHERE backtest_id = %s"
                rows = self._storage.execute(query, (backtest_id,))
                if rows and isinstance(rows, (list, tuple)):
                    raw_data = rows[0].get("data") if isinstance(rows[0], dict) else None
                    if raw_data:
                        data_dict = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
                        result = BacktestResult(**data_dict)
                        with self._lock:
                            self._by_id[backtest_id] = result
                        return result
            except Exception as e:
                logger.error("BacktestRepository: Failed to load backtest result %s: %s", backtest_id, e)
                raise BacktestRepositoryError(f"Failed to load backtest result from storage: {e}") from e

        return None

    def list_results(self) -> List[BacktestResult]:
        """Retrieve all persisted backtest results."""
        with self._lock:
            return list(self._history)
