"""Risk Metrics Engine computing Sharpe, Sortino, and Calmar ratios driven by AnalyticsContext (Sprint 8A-H)."""

from __future__ import annotations

import abc
import math
from typing import List, Optional

from backtesting_engine.analytics.models.analytics import AnalyticsContext, PerformanceMetrics, RiskMetrics


class IRiskMetricCalculator(abc.ABC):
    """Abstract interface for extensible risk metric calculators (Open/Closed Principle)."""

    @abc.abstractmethod
    def calculate(
        self,
        performance: PerformanceMetrics,
        daily_returns: List[float],
        max_drawdown: float,
        context: AnalyticsContext,
    ) -> float:
        """Calculate specific risk metric value using configuration context."""


class SharpeRatioCalculator(IRiskMetricCalculator):
    """Calculates annualized Sharpe Ratio using risk-free rate from AnalyticsContext."""

    def calculate(
        self,
        performance: PerformanceMetrics,
        daily_returns: List[float],
        max_drawdown: float,
        context: AnalyticsContext,
    ) -> float:
        if performance.volatility <= 0.0:
            return 0.0
        excess_return = performance.annualized_return - context.risk_free_rate
        return excess_return / performance.volatility


class SortinoRatioCalculator(IRiskMetricCalculator):
    """Calculates annualized Sortino Ratio focusing on downside volatility relative to risk_free_rate."""

    def calculate(
        self,
        performance: PerformanceMetrics,
        daily_returns: List[float],
        max_drawdown: float,
        context: AnalyticsContext,
    ) -> float:
        if not daily_returns:
            return 0.0

        rf_period = context.risk_free_rate / context.annualization_factor
        downside_diffs = [r - rf_period for r in daily_returns if (r - rf_period) < 0.0]

        if not downside_diffs:
            return 0.0

        n = len(daily_returns)
        sum_sq = sum(d ** 2 for d in downside_diffs)
        downside_variance = sum_sq / n
        downside_std = math.sqrt(downside_variance)
        downside_volatility = downside_std * math.sqrt(context.annualization_factor)

        if downside_volatility <= 0.0:
            return 0.0

        excess_return = performance.annualized_return - context.risk_free_rate
        return excess_return / downside_volatility


class CalmarRatioCalculator(IRiskMetricCalculator):
    """Calculates Calmar Ratio (CAGR / Max Drawdown)."""

    def calculate(
        self,
        performance: PerformanceMetrics,
        daily_returns: List[float],
        max_drawdown: float,
        context: AnalyticsContext,
    ) -> float:
        if max_drawdown <= 0.0:
            return 0.0
        return performance.cagr / max_drawdown


class RiskMetricsEngine:
    """Pure computational engine coordinating risk-adjusted return ratio calculations."""

    def __init__(
        self,
        sharpe_calc: Optional[IRiskMetricCalculator] = None,
        sortino_calc: Optional[IRiskMetricCalculator] = None,
        calmar_calc: Optional[IRiskMetricCalculator] = None,
    ) -> None:
        self._sharpe_calc = sharpe_calc or SharpeRatioCalculator()
        self._sortino_calc = sortino_calc or SortinoRatioCalculator()
        self._calmar_calc = calmar_calc or CalmarRatioCalculator()

    def calculate(
        self,
        performance: PerformanceMetrics,
        daily_returns: List[float],
        max_drawdown: float,
        context: Optional[AnalyticsContext] = None,
    ) -> RiskMetrics:
        """Calculate Sharpe, Sortino, and Calmar ratios strictly consuming AnalyticsContext."""
        ctx = context or AnalyticsContext()
        prec = ctx.decimal_precision

        sharpe = self._sharpe_calc.calculate(performance, daily_returns, max_drawdown, ctx)
        sortino = self._sortino_calc.calculate(performance, daily_returns, max_drawdown, ctx)
        calmar = self._calmar_calc.calculate(performance, daily_returns, max_drawdown, ctx)

        return RiskMetrics(
            sharpe_ratio=round(sharpe, prec),
            sortino_ratio=round(sortino, prec),
            calmar_ratio=round(calmar, prec),
        )
