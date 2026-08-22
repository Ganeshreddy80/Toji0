"""Monte Carlo Simulation Engine Orchestrator (Sprint 8C)."""

from __future__ import annotations

import logging
from typing import Optional

from backtesting_engine.core.models import BacktestResult
from backtesting_engine.monte_carlo.confidence import MonteCarloConfidenceEngine
from backtesting_engine.monte_carlo.models.monte_carlo import (
    MonteCarloConfig,
    MonteCarloReport,
)
from backtesting_engine.monte_carlo.risk import MonteCarloRiskEngine
from backtesting_engine.monte_carlo.simulator import MonteCarloSimulator
from backtesting_engine.monte_carlo.statistics import MonteCarloStatisticsEngine

logger = logging.getLogger(__name__)


class MonteCarloOrchestrator:
    """Authoritative orchestrator coordinating Monte Carlo simulations, statistics, confidence intervals, and risk analytics."""

    def __init__(
        self,
        simulator: Optional[MonteCarloSimulator] = None,
        statistics_engine: Optional[MonteCarloStatisticsEngine] = None,
        confidence_engine: Optional[MonteCarloConfidenceEngine] = None,
        risk_engine: Optional[MonteCarloRiskEngine] = None,
    ) -> None:
        self.simulator = simulator or MonteCarloSimulator()
        self.statistics_engine = statistics_engine or MonteCarloStatisticsEngine()
        self.confidence_engine = confidence_engine or MonteCarloConfidenceEngine()
        self.risk_engine = risk_engine or MonteCarloRiskEngine()

    def run(
        self,
        result: BacktestResult,
        config: Optional[MonteCarloConfig] = None,
    ) -> MonteCarloReport:
        """Run complete Monte Carlo simulation and analysis pipeline on BacktestResult.

        Args:
            result: Completed BacktestResult object.
            config: Optional simulation configuration parameters.

        Returns:
            Immutable MonteCarloReport containing all outputs.
        """
        if not result:
            raise ValueError("BacktestResult object cannot be None.")

        mc_config = config or MonteCarloConfig()

        if mc_config.iterations <= 0:
            raise ValueError(f"MonteCarloConfig iterations must be > 0, got {mc_config.iterations}.")

        # 1. Run Simulator
        simulations = self.simulator.simulate(result, config_override=mc_config)

        # 2. Compute Statistics
        stats_output = self.statistics_engine.compute_statistics(simulations)

        # 3. Compute Confidence Intervals
        confidence_intervals = self.confidence_engine.compute_confidence_intervals(
            simulations=simulations,
            confidence_levels=mc_config.confidence_levels,
        )

        # 4. Compute Risk Metrics
        risk_metrics = self.risk_engine.compute_risk_metrics(simulations)

        # 5. Assemble Summary
        summary = {
            **stats_output["summary"],
            **risk_metrics,
            "config": mc_config.model_dump(),
            "backtest_id": result.backtest_id,
            "total_simulations": len(simulations),
        }

        report = MonteCarloReport(
            simulations=simulations,
            confidence_intervals=confidence_intervals,
            risk_of_ruin=risk_metrics["probability_of_ruin"],
            expected_return=stats_output["expected_return"],
            expected_drawdown=stats_output["expected_drawdown"],
            percentile_table=stats_output["percentile_table"],
            summary=summary,
        )

        return report
