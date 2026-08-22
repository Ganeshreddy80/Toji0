"""Degradation Detection abstraction interface and rule-based detector (Sprint 8A-H)."""

from __future__ import annotations

import abc
from backtesting_engine.analytics.models.analytics import (
    AnalyticsContext,
    DrawdownMetrics,
    RiskMetrics,
    TradeStatistics,
)


class IDegradationDetector(abc.ABC):
    """Abstract protocol for evaluating strategy performance degradation (Open/Closed Principle)."""

    @abc.abstractmethod
    def detect_degradation(
        self,
        drawdown: DrawdownMetrics,
        trade_stats: TradeStatistics,
        risk: RiskMetrics,
        context: AnalyticsContext,
    ) -> bool:
        """Return True if strategy performance has degraded."""


class DefaultRuleBasedDegradationDetector(IDegradationDetector):
    """Default rule-based degradation detector assessing drawdown depth, win rate, and Sharpe ratio."""

    def __init__(
        self,
        max_drawdown_threshold: float = 0.25,
        min_win_rate_threshold: float = 0.35,
        min_trades_for_win_rate_rule: int = 5,
        min_sharpe_threshold: float = 0.0,
    ) -> None:
        self._max_drawdown_threshold = max_drawdown_threshold
        self._min_win_rate_threshold = min_win_rate_threshold
        self._min_trades_for_win_rate_rule = min_trades_for_win_rate_rule
        self._min_sharpe_threshold = min_sharpe_threshold

    def detect_degradation(
        self,
        drawdown: DrawdownMetrics,
        trade_stats: TradeStatistics,
        risk: RiskMetrics,
        context: AnalyticsContext,
    ) -> bool:
        """Evaluate strategy degradation against configured rule thresholds."""
        if drawdown.max_drawdown > self._max_drawdown_threshold:
            return True

        if (
            trade_stats.total_trades >= self._min_trades_for_win_rate_rule
            and trade_stats.win_rate < self._min_win_rate_threshold
        ):
            return True

        if (
            trade_stats.total_trades >= self._min_trades_for_win_rate_rule
            and risk.sharpe_ratio < self._min_sharpe_threshold
        ):
            return True

        return False
