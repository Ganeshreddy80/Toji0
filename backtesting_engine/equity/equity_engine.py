"""Account equity calculator, drawdown tracker, and return series generator (Sprint 7A)."""

from __future__ import annotations

import logging
import threading
from typing import List

from backtesting_engine.core.exceptions import EquityEngineError
from backtesting_engine.core.interfaces import IEquityEngine, ITradeLedger
from backtesting_engine.core.models import EquityPoint, MarketBar

logger = logging.getLogger(__name__)


class EquityEngine(IEquityEngine):
    """Tracks account equity snapshots, peak drawdowns, and produces return series for Research Platform."""

    def __init__(self, initial_capital: float = 100000.0) -> None:
        if initial_capital <= 0.0:
            raise EquityEngineError("Initial capital must be positive.")

        self._initial_capital = initial_capital
        self._peak_equity = initial_capital
        self._snapshots: List[EquityPoint] = []
        self._lock = threading.RLock()

    def update(self, current_bar: MarketBar, ledger: ITradeLedger) -> EquityPoint:
        """Update equity snapshot for the current replayed bar."""
        if not current_bar or not ledger:
            raise EquityEngineError("Valid MarketBar and TradeLedger required for equity calculation.")

        with self._lock:
            # Update unrealized PnL for open positions
            ledger.update_unrealized_pnl(current_bar)

            open_trades = ledger.get_open_trades()
            closed_trades = ledger.get_closed_trades()

            total_closed_pnl = sum(t.realized_pnl for t in closed_trades)
            total_open_pnl = sum(t.unrealized_pnl for t in open_trades)

            balance = round(self._initial_capital + total_closed_pnl, 4)
            current_equity = round(balance + total_open_pnl, 4)

            # Drawdown calculation
            if current_equity > self._peak_equity:
                self._peak_equity = current_equity

            drawdown = (self._peak_equity - current_equity) / self._peak_equity if self._peak_equity > 0.0 else 0.0
            drawdown = max(0.0, min(1.0, round(drawdown, 4)))

            snapshot = EquityPoint(
                timestamp=current_bar.timestamp,
                balance=balance,
                equity=current_equity,
                drawdown=drawdown,
                open_pnl=round(total_open_pnl, 4),
                closed_pnl=round(total_closed_pnl, 4),
                account_value=current_equity,
            )
            self._snapshots.append(snapshot)
            return snapshot

    def get_returns_series(self) -> List[float]:
        """Generate deterministic periodic return series for consumption by Research Platform."""
        with self._lock:
            if len(self._snapshots) <= 1:
                return []

            returns: List[float] = []
            for i in range(1, len(self._snapshots)):
                prev = self._snapshots[i - 1].equity
                curr = self._snapshots[i].equity
                r = (curr - prev) / prev if prev > 0.0 else 0.0
                returns.append(round(r, 6))
            return returns

    def get_equity_curve(self) -> List[float]:
        """Return account equity curve float series for consumption by Research Platform."""
        with self._lock:
            if not self._snapshots:
                return [self._initial_capital]
            return [s.equity for s in self._snapshots]

    def get_snapshots(self) -> List[EquityPoint]:
        """Retrieve all equity snapshot objects."""
        with self._lock:
            return list(self._snapshots)
