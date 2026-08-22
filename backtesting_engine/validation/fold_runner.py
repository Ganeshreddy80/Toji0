"""Fold Runner executing isolated walk-forward training and testing backtest folds (Sprint 8B)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backtesting_engine.analytics.metrics_engine import IPortfolioAnalyticsEngine, PortfolioAnalyticsEngine
from backtesting_engine.core.interfaces import IBacktestOrchestrator
from backtesting_engine.core.models import BacktestConfig, MarketBar
from backtesting_engine.core.orchestrator import BacktestOrchestrator
from backtesting_engine.validation.metrics import WalkForwardMetricsEngine
from backtesting_engine.validation.models.validation import FoldResult, ValidationWindow, WalkForwardConfig

logger = logging.getLogger(__name__)


class FoldRunner:
    """Pure computational runner executing single fold training and testing backtests."""

    def __init__(
        self,
        orchestrator: Optional[IBacktestOrchestrator] = None,
        analytics_engine: Optional[IPortfolioAnalyticsEngine] = None,
    ) -> None:
        self._orchestrator = orchestrator or BacktestOrchestrator()
        self._analytics_engine = analytics_engine or PortfolioAnalyticsEngine()

    def run_fold(
        self,
        window: ValidationWindow,
        bars: List[MarketBar],
        config: WalkForwardConfig,
        orders_to_place: Optional[List[Dict[str, Any]]] = None,
    ) -> FoldResult:
        """Execute training and testing backtest pipelines for a single validation window."""
        t_start = time.perf_counter()
        warnings: List[str] = []

        # Slice bars for train and test periods using window index boundaries
        train_bars = bars[window.train_start_idx : window.train_end_idx + 1]
        test_bars = bars[window.test_start_idx : window.test_end_idx + 1]

        # Construct BacktestConfig for train and test runs
        train_bt_cfg = BacktestConfig(
            name=f"WalkForward-Fold-{window.fold_number}-Train",
            start_date=window.train_start,
            end_date=window.train_end,
            seed=config.random_seed,
        )

        test_bt_cfg = BacktestConfig(
            name=f"WalkForward-Fold-{window.fold_number}-Test",
            start_date=window.test_start,
            end_date=window.test_end,
            seed=config.random_seed,
        )

        # Execute training backtest run
        train_result = self._orchestrator.run_backtest(
            config=train_bt_cfg,
            bars=train_bars,
            orders_to_place=orders_to_place,
        )
        train_metrics = self._analytics_engine.compute_analytics(train_result, context=config.context)

        # Execute testing backtest run
        test_result = self._orchestrator.run_backtest(
            config=test_bt_cfg,
            bars=test_bars,
            orders_to_place=orders_to_place,
        )
        test_metrics = self._analytics_engine.compute_analytics(test_result, context=config.context)

        train_trades_count = train_metrics.trade_stats.total_trades
        test_trades_count = test_metrics.trade_stats.total_trades

        # Warnings evaluation
        if test_trades_count < config.minimum_trades:
            warnings.append(
                f"Fold {window.fold_number} test trades count ({test_trades_count}) below minimum threshold ({config.minimum_trades})."
            )

        if test_metrics.degradation_detected:
            warnings.append(f"Fold {window.fold_number} test metrics exhibit performance degradation.")

        # Drift metrics calculation
        perf_drift, sharpe_drift, dd_drift, trade_drift = WalkForwardMetricsEngine.compute_fold_drift(
            train_return=train_metrics.performance.total_return,
            test_return=test_metrics.performance.total_return,
            train_sharpe=train_metrics.risk.sharpe_ratio,
            test_sharpe=test_metrics.risk.sharpe_ratio,
            train_dd=train_metrics.drawdown.max_drawdown,
            test_dd=test_metrics.drawdown.max_drawdown,
            train_trades=train_trades_count,
            test_trades=test_trades_count,
        )

        t_duration = max(0.0, time.perf_counter() - t_start)

        logger.info(
            "FoldRunner: Executed Fold %d (Train Ret=%.4f, Test Ret=%.4f, Test Sharpe=%.4f, Duration=%.2fs)",
            window.fold_number,
            train_metrics.performance.total_return,
            test_metrics.performance.total_return,
            test_metrics.risk.sharpe_ratio,
            t_duration,
        )

        return FoldResult(
            fold_number=window.fold_number,
            window=window,
            train_metrics=train_metrics,
            test_metrics=test_metrics,
            train_trades=train_trades_count,
            test_trades=test_trades_count,
            performance_drift=perf_drift,
            sharpe_drift=sharpe_drift,
            drawdown_drift=dd_drift,
            trade_count_drift=trade_drift,
            execution_time_seconds=round(t_duration, 4),
            warnings=warnings,
        )
