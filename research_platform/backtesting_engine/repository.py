"""Database repositories for backtesting runs, orders, and trades.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional

from research_platform.backtesting_engine.interfaces import IBacktestRepository
from research_platform.backtesting_engine.models import BacktestRun, Order, Trade


class BacktestRepository(IBacktestRepository):
    """Memory repository saving backtest runs, orders, and closed trades."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, BacktestRun] = {}
        self._orders: Dict[str, Order] = {}
        self._trades: Dict[str, List[Trade]] = {}

    def save_run(self, run: BacktestRun) -> None:
        with self._lock:
            self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[BacktestRun]:
        with self._lock:
            return self._runs.get(run_id)

    def list_runs(self) -> List[BacktestRun]:
        with self._lock:
            return list(self._runs.values())

    def save_order(self, order: Order) -> None:
        with self._lock:
            self._orders[order.order_id] = order

    def get_order(self, order_id: str) -> Optional[Order]:
        with self._lock:
            return self._orders.get(order_id)

    def save_trade(self, run_id: str, trade: Trade) -> None:
        with self._lock:
            if run_id not in self._trades:
                self._trades[run_id] = []
            self._trades[run_id].append(trade)

    def list_trades(self, run_id: str) -> List[Trade]:
        with self._lock:
            return list(self._trades.get(run_id, []))
