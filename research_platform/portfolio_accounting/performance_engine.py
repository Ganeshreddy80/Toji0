"""Performance Engine — calculates rich performance and volatility analytics.
"""

from __future__ import annotations

import logging
import math
from typing import List

from research_platform.portfolio_accounting.metrics_engine import MetricsEngine
from research_platform.portfolio_accounting.models import PortfolioMetrics, ValuatedPosition

logger = logging.getLogger(__name__)


class PerformanceEngine(MetricsEngine):
    """Calculates continuous performance metrics including Sortino, Drawdowns, and Rolling returns."""

    def compute(
        self,
        initial_balance: float,
        current_equity: float,
        positions: List[ValuatedPosition],
    ) -> PortfolioMetrics:
        # Get base metrics from MetricsEngine
        base = super().compute(initial_balance, current_equity, positions)

        with self._lock:
            curve = list(self._equity_curve)

        # Calculate loss rate
        loss_rate = base.losing_trades / base.total_trades if base.total_trades > 0 else 0.0

        # Calculate returns for volatility / Sharpe / Sortino
        returns = []
        if len(curve) >= 2:
            returns = [(curve[i] - curve[i - 1]) / curve[i - 1] for i in range(1, len(curve)) if curve[i - 1] != 0]

        # Sortino Ratio calculation
        sortino = 0.0
        if returns:
            mean_r = sum(returns) / len(returns)
            downside_returns = [r for r in returns if r < 0]
            downside_variance = sum(r**2 for r in downside_returns) / len(downside_returns) if downside_returns else 0.0
            downside_deviation = math.sqrt(downside_variance)
            if downside_deviation > 0:
                sortino = (mean_r / downside_deviation) * math.sqrt(252)

        # Daily and Monthly returns (approximated based on curve segments)
        daily_return = returns[-1] * 100.0 if returns else 0.0
        monthly_return = 0.0
        if len(returns) >= 20:
            monthly_return = (curve[-1] - curve[-20]) / curve[-20] * 100.0
        elif curve:
            monthly_return = (curve[-1] - initial_balance) / initial_balance * 100.0

        # Rolling returns / Volatility of the last 10 entries (2-week approximation)
        rolling_returns = 0.0
        rolling_vol = 0.0
        rolling_window = returns[-10:] if len(returns) >= 10 else returns
        if rolling_window:
            rolling_returns = sum(rolling_window) / len(rolling_window) * 100.0
            mean_rolling = sum(rolling_window) / len(rolling_window)
            var_rolling = sum((r - mean_rolling) ** 2 for r in rolling_window) / len(rolling_window)
            rolling_vol = math.sqrt(var_rolling) * math.sqrt(252) * 100.0

        return PortfolioMetrics(
            total_return_pct=base.total_return_pct,
            win_rate=base.win_rate,
            average_winner=base.average_winner,
            average_loser=base.average_loser,
            profit_factor=base.profit_factor,
            expectancy=base.expectancy,
            sharpe_ratio=base.sharpe_ratio,
            max_drawdown=base.max_drawdown,
            max_drawdown_pct=base.max_drawdown_pct,
            largest_winner=base.largest_winner,
            largest_loser=base.largest_loser,
            current_exposure=base.current_exposure,
            total_trades=base.total_trades,
            winning_trades=base.winning_trades,
            losing_trades=base.losing_trades,
            # Phase 16 additionals
            loss_rate=round(loss_rate, 4),
            sortino_ratio=round(sortino, 4),
            daily_return=round(daily_return, 4),
            monthly_return=round(monthly_return, 4),
            equity_curve=curve,
            rolling_volatility=round(rolling_vol, 4),
            rolling_returns=round(rolling_returns, 4),
        )
