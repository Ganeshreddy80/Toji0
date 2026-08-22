"""Walk-forward metrics aggregation and deterministic overfitting, stability, and consistency scoring (Sprint 8B)."""

from __future__ import annotations

import math
from typing import List

from backtesting_engine.validation.models.validation import FoldResult, WalkForwardConfig, WalkForwardReport


class WalkForwardMetricsEngine:
    """Pure computational engine for fold-drift metrics and deterministic overfitting, stability, and consistency scoring."""

    @staticmethod
    def compute_fold_drift(
        train_return: float,
        test_return: float,
        train_sharpe: float,
        test_sharpe: float,
        train_dd: float,
        test_dd: float,
        train_trades: int,
        test_trades: int,
    ) -> tuple[float, float, float, float]:
        """Compute individual fold performance drift, Sharpe drift, drawdown drift, and trade count drift."""
        denom_ret = abs(train_return) if abs(train_return) > 1e-8 else 1.0
        perf_drift = (test_return - train_return) / denom_ret
        sharpe_drift = test_sharpe - train_sharpe
        dd_drift = test_dd - train_dd

        denom_trades = max(1, train_trades)
        trade_drift = (test_trades - train_trades) / denom_trades

        return (
            round(perf_drift, 4),
            round(sharpe_drift, 4),
            round(dd_drift, 4),
            round(trade_drift, 4),
        )

    @staticmethod
    def compute_report(
        folds: List[FoldResult],
        config: WalkForwardConfig,
    ) -> WalkForwardReport:
        """Aggregate fold results and calculate deterministic overfitting, consistency, and stability scores."""
        if not folds:
            return WalkForwardReport(
                folds=[],
                average_train_return=0.0,
                average_test_return=0.0,
                average_drawdown=0.0,
                average_sharpe=0.0,
                stability_score=0.0,
                degradation_score=1.0,
                overfitting_score=100.0,
                consistency_score=0.0,
                passed=False,
                config=config,
            )

        n = len(folds)
        train_returns = [f.train_metrics.performance.total_return for f in folds]
        test_returns = [f.test_metrics.performance.total_return for f in folds]
        test_drawdowns = [f.test_metrics.drawdown.max_drawdown for f in folds]
        test_sharpes = [f.test_metrics.risk.sharpe_ratio for f in folds]
        degradations = [1.0 if f.test_metrics.degradation_detected else 0.0 for f in folds]

        avg_train_ret = sum(train_returns) / n
        avg_test_ret = sum(test_returns) / n
        avg_dd = sum(test_drawdowns) / n
        avg_sharpe = sum(test_sharpes) / n
        degradation_score = sum(degradations) / n

        # 1. Deterministic Overfitting Score [0.0, 100.0]
        # Measures performance collapse, Sharpe collapse, win rate collapse, and drawdown expansion
        ret_collapses = [max(0.0, tr - te) for tr, te in zip(train_returns, test_returns)]
        sharpe_collapses = [max(0.0, tr - te) for tr, te in zip([f.train_metrics.risk.sharpe_ratio for f in folds], test_sharpes)]
        dd_expansions = [max(0.0, te_dd - tr_dd) for tr_dd, te_dd in zip([f.train_metrics.drawdown.max_drawdown for f in folds], test_drawdowns)]
        win_collapses = [max(0.0, f.train_metrics.trade_stats.win_rate - f.test_metrics.trade_stats.win_rate) for f in folds]

        mean_ret_collapse = sum(ret_collapses) / n
        mean_sharpe_collapse = sum(sharpe_collapses) / n
        mean_dd_expansion = sum(dd_expansions) / n
        mean_win_collapse = sum(win_collapses) / n

        # Weighted index normalized to [0, 100]
        of_index = (
            mean_ret_collapse * 40.0 +
            mean_sharpe_collapse * 20.0 +
            mean_dd_expansion * 25.0 +
            mean_win_collapse * 15.0
        )
        overfitting_score = round(max(0.0, min(100.0, of_index * 100.0)), 2)

        # 2. Consistency Score [0.0, 100.0]
        # Evaluates fold-to-fold variance of test returns, test Sharpe ratios, and test drawdowns
        if n >= 2:
            var_ret = sum((r - avg_test_ret) ** 2 for r in test_returns) / (n - 1)
            var_sharpe = sum((s - avg_sharpe) ** 2 for s in test_sharpes) / (n - 1)
            var_dd = sum((d - avg_dd) ** 2 for d in test_drawdowns) / (n - 1)
            std_ret = math.sqrt(var_ret)
            std_sharpe = math.sqrt(var_sharpe)
            std_dd = math.sqrt(var_dd)
        else:
            std_ret = 0.0
            std_sharpe = 0.0
            std_dd = 0.0

        penalty = (std_ret * 200.0) + (std_sharpe * 20.0) + (std_dd * 100.0)
        consistency_score = round(max(0.0, min(100.0, 100.0 - penalty)), 2)

        # 3. Stability Score [0.0, 100.0]
        # Measures performance persistence (ratio of positive test returns), positive Sharpe ratio, and drawdown control
        positive_folds = sum(1 for r in test_returns if r > 0.0)
        pos_fold_ratio = positive_folds / n
        pos_sharpe_folds = sum(1 for s in test_sharpes if s > 0.0)
        pos_sharpe_ratio = pos_sharpe_folds / n

        st_index = (pos_fold_ratio * 40.0) + (pos_sharpe_ratio * 30.0) + ((1.0 - avg_dd) * 30.0)
        stability_score = round(max(0.0, min(100.0, st_index)), 2)

        # Pass / Fail Evaluation
        passed = (overfitting_score <= config.overfitting_threshold) and (stability_score >= config.stability_threshold)

        prec = config.context.decimal_precision

        return WalkForwardReport(
            folds=folds,
            average_train_return=round(avg_train_ret, prec),
            average_test_return=round(avg_test_ret, prec),
            average_drawdown=round(avg_dd, prec),
            average_sharpe=round(avg_sharpe, prec),
            stability_score=stability_score,
            degradation_score=round(degradation_score, prec),
            overfitting_score=overfitting_score,
            consistency_score=consistency_score,
            passed=passed,
            config=config,
            engine_version="1.0.0",
        )
