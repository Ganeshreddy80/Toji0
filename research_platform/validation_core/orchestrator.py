"""Validation Core Orchestrator implementation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from toji_platform.core.event_bus import IEventBus

from research_platform.validation_core.cv import TimeSeriesCVSplitter
from research_platform.validation_core.drift import DriftDetector
from research_platform.validation_core.events import (
    ResearchScoreUpdated,
    StrategyRejected,
    StrategyValidated,
    ValidationCompleted,
    ValidationFailed,
    ValidationStarted
)
from research_platform.validation_core.interfaces import IValidationCoreOrchestrator
from research_platform.validation_core.models import (
    CrossValidationResult,
    ResearchScore,
    StatisticalMetrics,
    ValidationDecision,
    ValidationReport,
    ValidationRun,
    ValidationSummary,
    ValidationConfiguration
)
from research_platform.validation_core.overfitting import OverfittingDetector
from research_platform.validation_core.regime import MarketRegimeClassifier
from research_platform.validation_core.repository import ValidationRepository
from research_platform.validation_core.robust_stats import RobustStatistics
from research_platform.validation_core.scoring import ResearchScoreCalculator
from research_platform.validation_core.sharpe import SharpeValidator
from research_platform.validation_core.statistical_testing import StatisticalTestingSuite

logger = logging.getLogger(__name__)


class ValidationCoreOrchestrator(IValidationCoreOrchestrator):
    """Central validator orchestrating cross-validations, overfitting tests, and robust statistics gates."""

    def __init__(self, event_bus: IEventBus) -> None:
        self._event_bus = event_bus
        self._repo = ValidationRepository()

    @property
    def repository(self) -> ValidationRepository:
        return self._repo

    def validate_strategy(
        self,
        config: ValidationConfiguration,
        dataset_id: str,
        returns: np.ndarray,
        all_trials_returns: Optional[List[np.ndarray]] = None
    ) -> ValidationReport:
        """Execute cross-validation, overfitting checks, and return validation reports."""
        run_id = str(uuid.uuid4())
        
        # Publish start event
        self._event_bus.publish(ValidationStarted(payload={"run_id": run_id, "backtest_id": config.backtest_id}))
        logger.info("Validation run %s started for backtest: %s", run_id, config.backtest_id)

        try:
            # 1. Cross Validation splits (CPCV)
            splits = TimeSeriesCVSplitter.cpcv_split(len(returns), num_partitions=6, num_test_partitions=2)
            cv_results = []
            
            for idx, (train_ranges, test_range) in enumerate(splits):
                # Slice train and test returns
                train_slices = []
                for start, end in train_ranges:
                    train_slices.append(returns[start:end])
                
                train_ret = np.concatenate(train_slices) if train_slices else np.array([])
                test_ret = returns[test_range[0]:test_range[1]]

                train_sr = np.mean(train_ret) / (np.std(train_ret) + 1e-10) * np.sqrt(252.0) if len(train_ret) > 1 else 0.0
                test_sr = np.mean(test_ret) / (np.std(test_ret) + 1e-10) * np.sqrt(252.0) if len(test_ret) > 1 else 0.0

                cv_results.append(
                    CrossValidationResult(
                        split_index=idx,
                        train_sharpe=float(train_sr),
                        test_sharpe=float(test_sr),
                        train_samples=len(train_ret),
                        test_samples=len(test_ret)
                    )
                )

            # 2. Probability of Backtest Overfitting (PBO)
            # Default mock trials returns if not provided
            trials = all_trials_returns or [returns, returns * 0.9, returns * 1.1]
            pbo = OverfittingDetector.calculate_pbo(trials, num_splits=5)

            # 3. Sharpe, PSR, and DSR metrics
            observed_srs = [np.mean(t) / (np.std(t) + 1e-10) * np.sqrt(252.0) for t in trials]
            psr = SharpeValidator.calculate_psr(list(returns), benchmark_sr=0.0)
            dsr = SharpeValidator.calculate_dsr(list(returns), observed_srs)

            # 4. Statistical Testing (Hansen SPA & White Reality Check)
            benchmark = np.zeros(len(returns))  # zero excess baseline
            spa_p = StatisticalTestingSuite.hansen_spa_test(returns, benchmark, trials[:2], num_bootstrap=20)
            wrc_p = StatisticalTestingSuite.white_reality_check(returns, benchmark, trials[:2], num_bootstrap=20)

            # 5. Robust Standard Errors (Newey-West HAC)
            robust_t, robust_se = RobustStatistics.newey_west_t_stat(returns)

            # 6. Drift Detection
            # Split returns in half to simulate drift baseline vs target
            half = len(returns) // 2
            drift_res = DriftDetector.detect_drift("returns", returns[:half], returns[half:])

            # 7. Market Regime performance
            sim_pnl = np.cumsum(returns)
            regime_res = MarketRegimeClassifier.evaluate_regimes(returns, sim_pnl)

            # 8. Research Score computation
            r_score = ResearchScoreCalculator.calculate(
                quality=0.9,
                freshness=0.95,
                drift_psi=drift_res.psi,
                pbo=pbo,
                psr=psr,
                dsr=dsr,
                spa_p_value=spa_p,
                regime_stability=0.9,
                weights=config.weights
            )
            self._event_bus.publish(
                ResearchScoreUpdated(payload={"backtest_id": config.backtest_id, "score": r_score.score_value})
            )

            # 9. Gatekeeper decisions
            decisions = [
                ValidationDecision(
                    check_name="DSR Check",
                    status="PASSED" if dsr > 0.4 else "FAILED",
                    detail=f"Deflated Sharpe Ratio is {dsr:.4f} (threshold: 0.40)"
                ),
                ValidationDecision(
                    check_name="PBO Check",
                    status="PASSED" if pbo < 0.3 else "FAILED",
                    detail=f"Probability of Overfitting is {pbo:.4f} (threshold: 0.30)"
                ),
                ValidationDecision(
                    check_name="Robust t-statistic",
                    status="PASSED" if abs(robust_t) >= 1.96 else "FAILED",
                    detail=f"Newey-West HAC t-statistic is {robust_t:.4f} (threshold: 1.96)"
                )
            ]

            is_approved = all(d.status == "PASSED" for d in decisions)

            # Construct final report
            obs_change = np.diff(sim_pnl)
            summary = ValidationSummary(
                total_runs=len(cv_results),
                pass_ratio=float(sum(1 for c in cv_results if c.test_sharpe > 0.0) / len(cv_results)),
                avg_sharpe=float(np.mean([c.test_sharpe for c in cv_results])),
                max_drawdown=float(np.max((np.maximum.accumulate(sim_pnl) - sim_pnl) / (np.maximum.accumulate(sim_pnl) + 1e-10))) if len(sim_pnl) > 0 else 0.0
            )

            stats_metrics = StatisticalMetrics(
                sharpe=float(np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252.0)) if len(returns) > 0 else 0.0,
                psr=psr,
                dsr=dsr,
                pbo=pbo,
                spa_p_value=spa_p,
                reality_check_p_value=wrc_p,
                robust_t_stat=robust_t
            )

            report = ValidationReport(
                report_id=str(uuid.uuid4()),
                backtest_id=config.backtest_id,
                summary=summary,
                decisions=decisions,
                metrics=stats_metrics,
                cv_results=cv_results,
                regime_results=regime_res,
                drift_results=[drift_res],
                research_score=r_score,
                is_approved=is_approved,
                timestamp=datetime.now(timezone.utc)
            )

            # Persist run
            run = ValidationRun(
                run_id=run_id,
                configuration=config,
                status="COMPLETED",
                report=report,
                timestamp=datetime.now(timezone.utc)
            )
            self._repo.save_run(run)

            # Publish event outcomes
            if is_approved:
                self._event_bus.publish(StrategyValidated(payload={"backtest_id": config.backtest_id}))
            else:
                self._event_bus.publish(StrategyRejected(payload={"backtest_id": config.backtest_id, "reason": "Failed statistical gates."}))

            self._event_bus.publish(ValidationCompleted(payload={"run_id": run_id, "approved": is_approved}))
            return report

        except Exception as e:
            logger.error("Validation Core execution failed: %s", e)
            self._event_bus.publish(ValidationFailed(payload={"run_id": run_id, "error": str(e)}))
            # Persist failed run
            run_failed = ValidationRun(
                run_id=run_id,
                configuration=config,
                status="FAILED",
                timestamp=datetime.now(timezone.utc)
            )
            self._repo.save_run(run_failed)
            raise e
