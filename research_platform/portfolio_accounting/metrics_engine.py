"""Metrics Engine — continuously computed institutional portfolio statistics."""

from __future__ import annotations

import logging
import math
import threading
from typing import List, Optional

from research_platform.portfolio_accounting.interfaces import IMetricsEngine
from research_platform.portfolio_accounting.models import (
    PortfolioMetrics,
    TradeRecord,
    ValuatedPosition,
)

logger = logging.getLogger(__name__)


class MetricsEngine(IMetricsEngine):
    """Computes portfolio performance metrics from completed trade records.

    All computations are pure in-memory arithmetic.
    Thread-safe: same RLock used for ingestion and computation.
    """

    def __init__(self) -> None:
        self._trades: List[TradeRecord] = []
        self._equity_curve: List[float] = []  # for Sharpe / Drawdown
        self._peak_equity: float = 0.0
        self._max_drawdown: float = 0.0
        self._max_drawdown_pct: float = 0.0
        self._lock = threading.RLock()

    # ── IMetricsEngine ────────────────────────────────────────────────────────

    def ingest_trade(self, trade: TradeRecord) -> None:
        with self._lock:
            self._trades.append(trade)

    def record_equity(self, equity: float) -> None:
        """Record current equity for drawdown and Sharpe computation."""
        with self._lock:
            self._equity_curve.append(equity)
            if equity > self._peak_equity:
                self._peak_equity = equity
            if self._peak_equity > 0:
                dd = self._peak_equity - equity
                dd_pct = dd / self._peak_equity
                if dd > self._max_drawdown:
                    self._max_drawdown = dd
                if dd_pct > self._max_drawdown_pct:
                    self._max_drawdown_pct = dd_pct

    def compute(
        self,
        initial_balance: float,
        current_equity: float,
        positions: List[ValuatedPosition],
    ) -> PortfolioMetrics:
        with self._lock:
            trades = list(self._trades)

        winners = [t for t in trades if t.net_pnl > 0]
        losers  = [t for t in trades if t.net_pnl <= 0]

        total_trades = len(trades)
        win_rate = len(winners) / total_trades if total_trades > 0 else 0.0

        avg_winner = (sum(t.net_pnl for t in winners) / len(winners)) if winners else 0.0
        avg_loser  = (sum(t.net_pnl for t in losers)  / len(losers))  if losers  else 0.0

        gross_profit = sum(t.net_pnl for t in winners)
        gross_loss   = abs(sum(t.net_pnl for t in losers))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

        # Expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        expectancy = (win_rate * avg_winner) + ((1 - win_rate) * avg_loser)

        largest_winner = max((t.net_pnl for t in winners), default=0.0)
        largest_loser  = min((t.net_pnl for t in losers),  default=0.0)

        # Sharpe ratio (annualised, simplified from equity curve returns)
        sharpe = self._compute_sharpe()

        total_return_pct = ((current_equity - initial_balance) / initial_balance * 100.0
                            if initial_balance > 0 else 0.0)

        current_exposure = sum(p.market_value for p in positions)

        with self._lock:
            md = self._max_drawdown
            md_pct = self._max_drawdown_pct

        return PortfolioMetrics(
            total_return_pct=round(total_return_pct, 4),
            win_rate=round(win_rate, 4),
            average_winner=round(avg_winner, 4),
            average_loser=round(avg_loser, 4),
            profit_factor=round(min(profit_factor, 9999.0), 4),
            expectancy=round(expectancy, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(md, 4),
            max_drawdown_pct=round(md_pct * 100, 4),
            largest_winner=round(largest_winner, 4),
            largest_loser=round(largest_loser, 4),
            current_exposure=round(current_exposure, 4),
            total_trades=total_trades,
            winning_trades=len(winners),
            losing_trades=len(losers),
        )

    # ── Internals ────────────────────────────────────────────────────────────

    def _compute_sharpe(self, risk_free_rate: float = 0.0) -> float:
        """Annualised Sharpe from equity curve.  Requires >= 2 data points."""
        with self._lock:
            curve = list(self._equity_curve)
        if len(curve) < 2:
            return 0.0
        returns = [(curve[i] - curve[i - 1]) / curve[i - 1]
                   for i in range(1, len(curve)) if curve[i - 1] != 0]
        if not returns:
            return 0.0
        n = len(returns)
        mean_r = sum(returns) / n
        variance = sum((r - mean_r) ** 2 for r in returns) / n
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        if std_r == 0:
            return 0.0
        # Annualise assuming ~252 trading days, each tick is ~1 day (approximation)
        return ((mean_r - risk_free_rate) / std_r) * math.sqrt(252)
