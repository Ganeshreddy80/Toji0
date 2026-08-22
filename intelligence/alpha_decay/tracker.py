"""Alpha Decay Tracker for evaluating performance degradation over time."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


class PerformancePoint(BaseModel):
    """Represent strategy performance metrics at a specific timestamp."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sharpe: float = Field(...)
    win_rate: float = Field(..., ge=0.0, le=1.0)
    returns: float = Field(...)

    model_config = {"frozen": True}


class AlphaDecayTracker:
    """Tracks strategy edge degradation over time using rolling performance analysis and linear regression trends."""

    def __init__(
        self,
        min_history_length: int = 5,
        sharpe_retirement_threshold: float = 0.5,
        win_rate_retirement_threshold: float = 0.40,
        decay_threshold: float = 0.35,  # 35% drop from baseline
    ) -> None:
        """Initialize the AlphaDecayTracker.

        Args:
            min_history_length: Minimum data points required to calculate decay.
            sharpe_retirement_threshold: Retire if rolling Sharpe drops below this.
            win_rate_retirement_threshold: Retire if rolling win rate drops below this.
            decay_threshold: Retire if Sharpe decays by this percentage from baseline.
        """
        self.min_history_length = min_history_length
        self.sharpe_retirement_threshold = sharpe_retirement_threshold
        self.win_rate_retirement_threshold = win_rate_retirement_threshold
        self.decay_threshold = decay_threshold
        self._history: dict[str, list[PerformancePoint]] = {}

    def record_performance(
        self,
        strategy_id: str,
        sharpe: float,
        win_rate: float,
        returns: float,
        timestamp: datetime | None = None,
    ) -> None:
        """Record a strategy performance observation.

        Args:
            strategy_id: Unique strategy identifier.
            sharpe: Sharpe ratio.
            win_rate: Win rate (0.0 to 1.0).
            returns: Return percentage.
            timestamp: Time of observation. Defaults to UTC now.
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if strategy_id not in self._history:
            self._history[strategy_id] = []

        self._history[strategy_id].append(
            PerformancePoint(
                timestamp=timestamp,
                sharpe=sharpe,
                win_rate=win_rate,
                returns=returns,
            )
        )
        # Keep sorted by timestamp
        self._history[strategy_id].sort(key=lambda x: x.timestamp)

    def _calculate_trend_slope(self, values: list[float]) -> float:
        """Helper to calculate simple linear regression slope of a series."""
        n = len(values)
        if n < 2:
            return 0.0
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x_val - x_mean) ** 2 for x_val in x)
        if denominator == 0.0:
            return 0.0
        return numerator / denominator

    def evaluate_decay(self, strategy_id: str) -> dict[str, Any]:
        """Evaluate strategy decay metrics and return a retirement recommendation.

        Args:
            strategy_id: Unique strategy identifier.

        Returns:
            Dictionary report containing baseline performance, current performance,
            decay percentage, trend slope, and a retirement recommendation flag.
        """
        history = self._history.get(strategy_id, [])
        if len(history) < self.min_history_length:
            return {
                "strategy_id": strategy_id,
                "should_retire": False,
                "reason": f"Insufficient history: {len(history)}/{self.min_history_length} points recorded",
                "decay_rate": 0.0,
                "sharpe_slope": 0.0,
            }

        # 1. Baseline vs Current
        # Baseline is average of first 3 runs
        baseline_points = history[:3]
        baseline_sharpe = sum(p.sharpe for p in baseline_points) / len(baseline_points)
        baseline_win_rate = sum(p.win_rate for p in baseline_points) / len(baseline_points)

        # Recent is average of last 3 runs
        recent_points = history[-3:]
        recent_sharpe = sum(p.sharpe for p in recent_points) / len(recent_points)
        recent_win_rate = sum(p.win_rate for p in recent_points) / len(recent_points)

        # 2. Decay calculations
        decay_rate = 0.0
        if baseline_sharpe > 0.0:
            decay_rate = (baseline_sharpe - recent_sharpe) / baseline_sharpe

        # 3. Slope regression (direction of Sharpe ratio over all observations)
        sharpe_values = [p.sharpe for p in history]
        slope = self._calculate_trend_slope(sharpe_values)

        # 4. Retirement logic
        should_retire = False
        reason = "Performance stable"

        if recent_sharpe < self.sharpe_retirement_threshold:
            should_retire = True
            reason = f"Sharpe ratio ({recent_sharpe:.2f}) dropped below retirement threshold ({self.sharpe_retirement_threshold})"
        elif recent_win_rate < self.win_rate_retirement_threshold:
            should_retire = True
            reason = f"Win rate ({recent_win_rate:.2%}) dropped below retirement threshold ({self.win_rate_retirement_threshold:.2%})"
        elif decay_rate > self.decay_threshold:
            should_retire = True
            reason = f"Sharpe ratio decayed by {decay_rate:.2%} from baseline ({baseline_sharpe:.2f} -> {recent_sharpe:.2f})"
        elif slope < -0.15:
            # Significant downwards trend
            should_retire = True
            reason = f"Significant negative slope ({slope:.4f}) in strategy Sharpe ratio over time"

        return {
            "strategy_id": strategy_id,
            "baseline_sharpe": baseline_sharpe,
            "baseline_win_rate": baseline_win_rate,
            "recent_sharpe": recent_sharpe,
            "recent_win_rate": recent_win_rate,
            "decay_rate": decay_rate,
            "sharpe_slope": slope,
            "should_retire": should_retire,
            "reason": reason,
        }
