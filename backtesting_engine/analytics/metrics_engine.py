"""Authoritative Portfolio Analytics Engine coordinating complete analytics computation (Sprint 8A-H)."""

from __future__ import annotations

import abc
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from backtesting_engine.analytics.benchmark import DefaultBenchmarkProvider, IBenchmarkProvider
from backtesting_engine.analytics.degradation import DefaultRuleBasedDegradationDetector, IDegradationDetector
from backtesting_engine.analytics.drawdown import DrawdownEngine
from backtesting_engine.analytics.equity_curve import EquityCurveEngine
from backtesting_engine.analytics.models.analytics import (
    AnalyticsContext,
    AnalyticsReport,
    BenchmarkComparison,
    DrawdownMetrics,
    EquityCurveAnalysis,
    PerformanceMetrics,
    PortfolioStatistics,
    RiskMetrics,
    SymbolPerformance,
    TradeStatistics,
)
from backtesting_engine.analytics.performance_metrics import PerformanceMetricsEngine
from backtesting_engine.analytics.portfolio_statistics import PortfolioStatisticsEngine
from backtesting_engine.analytics.risk_metrics import RiskMetricsEngine
from backtesting_engine.analytics.trade_statistics import TradeStatisticsEngine
from backtesting_engine.core.models import BacktestConfig, BacktestResult, EquityPoint, SimulatedFill, TradeRecord

logger = logging.getLogger(__name__)


class IPortfolioAnalyticsEngine(abc.ABC):
    """Protocol for portfolio analytics computation."""

    @abc.abstractmethod
    def compute_analytics(
        self,
        result: BacktestResult,
        context: Optional[AnalyticsContext] = None,
    ) -> AnalyticsReport:
        """Compute structured analytics report from backtest result."""

    @abc.abstractmethod
    def compute_from_components(
        self,
        backtest_id: str,
        snapshots: List[EquityPoint],
        trades: List[TradeRecord],
        fills: List[SimulatedFill],
        config: Optional[BacktestConfig] = None,
        context: Optional[AnalyticsContext] = None,
    ) -> AnalyticsReport:
        """Compute structured analytics report from raw backtest result components."""


class PortfolioAnalyticsEngine(IPortfolioAnalyticsEngine):
    """Authoritative analytics engine for portfolio, trade, risk, and drawdown calculations."""

    def __init__(
        self,
        equity_engine: Optional[EquityCurveEngine] = None,
        drawdown_engine: Optional[DrawdownEngine] = None,
        performance_engine: Optional[PerformanceMetricsEngine] = None,
        risk_engine: Optional[RiskMetricsEngine] = None,
        trade_engine: Optional[TradeStatisticsEngine] = None,
        portfolio_engine: Optional[PortfolioStatisticsEngine] = None,
        degradation_detector: Optional[IDegradationDetector] = None,
        benchmark_provider: Optional[IBenchmarkProvider] = None,
    ) -> None:
        self._equity_engine = equity_engine or EquityCurveEngine()
        self._drawdown_engine = drawdown_engine or DrawdownEngine()
        self._performance_engine = performance_engine or PerformanceMetricsEngine()
        self._risk_engine = risk_engine or RiskMetricsEngine()
        self._trade_engine = trade_engine or TradeStatisticsEngine()
        self._portfolio_engine = portfolio_engine or PortfolioStatisticsEngine()
        self._degradation_detector = degradation_detector or DefaultRuleBasedDegradationDetector()
        self._benchmark_provider = benchmark_provider or DefaultBenchmarkProvider()

    def compute_analytics(
        self,
        result: BacktestResult,
        context: Optional[AnalyticsContext] = None,
    ) -> AnalyticsReport:
        """Compute structured analytics report from a BacktestResult object."""
        if not result:
            raise ValueError("Invalid BacktestResult provided for analytics computation.")

        return self.compute_from_components(
            backtest_id=result.backtest_id,
            snapshots=result.equity_snapshots,
            trades=result.trades,
            fills=result.fills,
            config=result.config,
            context=context,
        )

    def compute_from_components(
        self,
        backtest_id: str,
        snapshots: List[EquityPoint],
        trades: List[TradeRecord],
        fills: List[SimulatedFill],
        config: Optional[BacktestConfig] = None,
        context: Optional[AnalyticsContext] = None,
    ) -> AnalyticsReport:
        """Compute structured analytics report from raw pipeline outputs using AnalyticsContext."""
        ctx = context or AnalyticsContext()
        initial_capital = config.initial_capital if config else 100000.0
        strategy_id = config.parameters.get("strategy_id", "strategy-default") if config and config.parameters else "strategy-default"

        # 1. Equity Curve Analysis
        equity_curve = self._equity_engine.calculate(snapshots=snapshots, initial_capital=initial_capital, context=ctx)

        # 2. Drawdown Analysis
        drawdown = self._drawdown_engine.calculate(snapshots=snapshots, initial_capital=initial_capital, context=ctx)

        # 3. Performance Metrics
        performance = self._performance_engine.calculate(
            snapshots=snapshots,
            daily_returns=equity_curve.daily_returns,
            initial_capital=initial_capital,
            context=ctx,
        )

        # 4. Risk Metrics
        risk = self._risk_engine.calculate(
            performance=performance,
            daily_returns=equity_curve.daily_returns,
            max_drawdown=drawdown.max_drawdown,
            context=ctx,
        )

        # 5. Trade Statistics
        trade_stats = self._trade_engine.calculate(trades=trades, context=ctx)

        # 6. Portfolio Allocation & Turnover Statistics
        portfolio_stats = self._portfolio_engine.calculate(
            snapshots=snapshots,
            fills=fills,
            initial_capital=initial_capital,
            context=ctx,
        )

        # 7. Symbol Performance Models for Mission Control (CTO Finding 5)
        symbol_map: Dict[str, SymbolPerformance] = {}
        symbol_trades: Dict[str, List[TradeRecord]] = {}

        for tr in trades:
            symbol_trades.setdefault(tr.symbol, []).append(tr)

        for sym, tr_list in symbol_trades.items():
            sym_pnls = [t.realized_pnl for t in tr_list]
            sym_net_pnl = sum(sym_pnls)
            sym_wins = sum(1 for p in sym_pnls if p > 0.0)
            sym_losses = sum(1 for p in sym_pnls if p < 0.0)
            sym_count = len(tr_list)
            sym_avg = sym_net_pnl / sym_count if sym_count > 0 else 0.0
            sym_max_win = max([p for p in sym_pnls if p > 0.0], default=0.0)
            sym_max_loss = min([p for p in sym_pnls if p < 0.0], default=0.0)
            sym_ret_pct = sym_net_pnl / initial_capital if initial_capital > 0.0 else 0.0

            symbol_map[sym] = SymbolPerformance(
                symbol=sym,
                net_pnl=round(sym_net_pnl, ctx.decimal_precision),
                return_pct=round(sym_ret_pct, ctx.decimal_precision),
                trade_count=sym_count,
                wins=sym_wins,
                losses=sym_losses,
                average_trade=round(sym_avg, ctx.decimal_precision),
                largest_win=round(sym_max_win, ctx.decimal_precision),
                largest_loss=round(sym_max_loss, ctx.decimal_precision),
                current_drawdown=0.0,
                exposure=0.0,
            )

        # 8. Performance degradation detection via IDegradationDetector interface (CTO Finding 6)
        degradation = self._degradation_detector.detect_degradation(
            drawdown=drawdown,
            trade_stats=trade_stats,
            risk=risk,
            context=ctx,
        )

        # 9. Benchmark comparison via IBenchmarkProvider interface (CTO Finding 7)
        benchmark_comp = self._benchmark_provider.calculate_benchmark_comparison(
            portfolio_returns=equity_curve.daily_returns,
            portfolio_total_return=performance.total_return,
            context=ctx,
        )

        now_utc = datetime.now(timezone.utc)

        report = AnalyticsReport(
            backtest_id=backtest_id,
            strategy_id=strategy_id,
            engine_version=ctx.engine_version,
            configuration_hash=ctx.configuration_hash,
            performance=performance,
            risk=risk,
            trade_stats=trade_stats,
            portfolio_stats=portfolio_stats,
            drawdown=drawdown,
            equity_curve=equity_curve,
            degradation_detected=degradation,
            symbol_performance=symbol_map,
            benchmark=benchmark_comp,
            context=ctx,
            generated_at=now_utc,
        )

        logger.info(
            "PortfolioAnalyticsEngine: Computed analytics report v%s for backtest %s (Total Return=%.4f, MaxDD=%.4f, Sharpe=%.4f, Rf=%.4f)",
            ctx.engine_version,
            backtest_id,
            performance.total_return,
            drawdown.max_drawdown,
            risk.sharpe_ratio,
            ctx.risk_free_rate,
        )
        return report
