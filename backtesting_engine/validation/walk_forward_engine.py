"""Authoritative Walk-Forward Validation Engine coordinating window generation, fold execution, and scoring (Sprint 8B)."""

from __future__ import annotations

import abc
import logging
from typing import Any, Dict, List, Optional

from backtesting_engine.core.models import MarketBar
from backtesting_engine.validation.fold_runner import FoldRunner
from backtesting_engine.validation.metrics import WalkForwardMetricsEngine
from backtesting_engine.validation.models.validation import (
    FoldResult,
    WalkForwardConfig,
    WalkForwardReport,
)
from backtesting_engine.validation.window_generator import WindowGenerator

logger = logging.getLogger(__name__)


class IWalkForwardEngine(abc.ABC):
    """Abstract protocol for Walk-Forward Validation Engine."""

    @abc.abstractmethod
    def run_walk_forward(
        self,
        bars: List[MarketBar],
        config: WalkForwardConfig,
        orders_to_place: Optional[List[Dict[str, Any]]] = None,
    ) -> WalkForwardReport:
        """Execute end-to-end walk-forward validation across replayed historical market bars."""


class WalkForwardEngine(IWalkForwardEngine):
    """Authoritative Walk-Forward Validation Engine orchestrating window generation, fold execution, and scoring."""

    def __init__(
        self,
        window_generator: Optional[WindowGenerator] = None,
        fold_runner: Optional[FoldRunner] = None,
        metrics_engine: Optional[WalkForwardMetricsEngine] = None,
    ) -> None:
        self._window_generator = window_generator or WindowGenerator()
        self._fold_runner = fold_runner or FoldRunner()
        self._metrics_engine = metrics_engine or WalkForwardMetricsEngine()

    def run_walk_forward(
        self,
        bars: List[MarketBar],
        config: WalkForwardConfig,
        orders_to_place: Optional[List[Dict[str, Any]]] = None,
    ) -> WalkForwardReport:
        """Execute walk-forward validation pipeline end-to-end and produce an immutable WalkForwardReport."""
        # 1. Generate chronological non-overlapping validation windows
        windows = self._window_generator.generate_windows(bars, config)

        # 2. Execute isolated backtest folds sequentially
        fold_results: List[FoldResult] = []
        for win in windows:
            result = self._fold_runner.run_fold(
                window=win,
                bars=bars,
                config=config,
                orders_to_place=orders_to_place,
            )
            fold_results.append(result)

        # 3. Aggregate metrics and compute deterministic overfitting, consistency, and stability scores
        report = self._metrics_engine.compute_report(folds=fold_results, config=config)

        logger.info(
            "WalkForwardEngine: Completed validation (%d folds, Avg Test Return=%.4f, Overfitting=%.2f, Stability=%.2f, Passed=%s)",
            len(report.folds),
            report.average_test_return,
            report.overfitting_score,
            report.stability_score,
            report.passed,
        )

        return report
