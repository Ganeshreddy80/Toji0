"""Optimization Engine Orchestrator implementing sweeps, Pareto ranking, and walk-forwards.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

from toji_platform.core.event_bus import IEventBus

from research_platform.backtesting_engine.models import BacktestConfiguration, CommissionModel, MarginModel, SlippageModel
from research_platform.backtesting_engine.orchestrator import BacktestingEngineOrchestrator
from research_platform.optimization_engine.algorithms import (
    BayesianOptimizerProxy,
    GeneticAlgorithmOptimizer,
    GridSearchOptimizer,
    RandomSearchOptimizer
)
from research_platform.optimization_engine.events import (
    OptimizationCompleted,
    OptimizationStarted,
    ParetoFrontUpdated,
    TrialEvaluated,
    WalkForwardCompleted
)
from research_platform.optimization_engine.models import (
    ConstraintResult,
    ObjectiveScore,
    OptimizationConfiguration,
    OptimizationResult,
    OptimizationRun,
    OptimizationTrial,
    ParameterCombination,
    ParetoFront,
    RobustnessMetrics
)
from research_platform.optimization_engine.repository import OptimizationRepository
from research_platform.optimization_engine.robustness import RobustnessAnalyzer
from research_platform.optimization_engine.walk_forward import WalkForwardOptimizer
from research_platform.strategy_lab.models import EntryRule, ExitRule, PositionSizingRule, StrategyDefinition

logger = logging.getLogger(__name__)


class OptimizationEngineOrchestrator:
    """Dispatches parameter scans, updates Pareto front maps, and retrains rolling windows."""

    def __init__(self, event_bus: IEventBus, backtester: BacktestingEngineOrchestrator) -> None:
        self._event_bus = event_bus
        self._backtester = backtester
        self._repo = OptimizationRepository()

    @property
    def repository(self) -> OptimizationRepository:
        return self._repo

    def run_optimization(
        self,
        config: OptimizationConfiguration,
        data_df: pd.DataFrame,
        strategy: StrategyDefinition,
        start_time: datetime,
        end_time: datetime
    ) -> OptimizationResult:
        """Run the strategy parameters optimization sweep."""
        run_id = str(uuid.uuid4())
        self._event_bus.publish(OptimizationStarted(payload={"run_id": run_id}))

        # 1. Resolve search algorithm
        if config.algorithm == "GRID":
            opt = GridSearchOptimizer()
        elif config.algorithm == "RANDOM":
            opt = RandomSearchOptimizer()
        elif config.algorithm == "GENETIC":
            opt = GeneticAlgorithmOptimizer()
        else:
            opt = BayesianOptimizerProxy()

        combinations = opt.generate_combinations(config)
        trials: List[OptimizationTrial] = []

        # 2. Evaluate trials (using backtesting engine)
        for i, combo in enumerate(combinations):
            trial_id = f"{run_id}_trial_{i}"

            # Create modified strategy overriding params with combo values
            modified_rules = []
            for rule in strategy.entry_rules:
                updated_params = rule.parameters.copy()
                for k, v in combo.values.items():
                    if k in updated_params:
                        updated_params[k] = v
                modified_rules.append(
                    EntryRule(
                        name=rule.name,
                        condition_type=rule.condition_type,
                        parameters=updated_params
                    )
                )

            mod_strategy = StrategyDefinition(
                strategy_id=strategy.strategy_id,
                name=strategy.name,
                display_name=strategy.display_name,
                description=strategy.description,
                version=strategy.version,
                entry_rules=modified_rules,
                exit_rules=strategy.exit_rules,
                sizing_rule=strategy.sizing_rule,
                risk_rules=strategy.risk_rules
            )

            # Backtester Configuration
            backtest_cfg = BacktestConfiguration(
                strategy_id=strategy.strategy_id,
                dataset_id="ds_1",
                initial_capital=10000.0,
                start_time=start_time,
                end_time=end_time,
                slippage=SlippageModel(type="Percentage", params={"percentage": 0.0005}),
                commission=CommissionModel(type="Percentage", params={"percentage": 0.001}),
                margin=MarginModel(initial_margin_pct=0.5, maintenance_margin_pct=0.3)
            )

            # Run backtest
            try:
                res = self._backtester.run_backtest(backtest_cfg, data_df, mod_strategy)
                composite = res.stats.sharpe_ratio + res.stats.cagr * 100
                is_valid = True
                violation_details = ""
            except Exception as e:
                logger.error("Trial backtest failed: %s", e)
                composite = -99.0
                is_valid = False
                violation_details = str(e)

            obj_score = ObjectiveScore(
                metrics={"Sharpe": res.stats.sharpe_ratio, "CAGR": res.stats.cagr} if is_valid else {},
                composite_score=composite
            )

            trial = OptimizationTrial(
                trial_id=trial_id,
                parameters=combo,
                score=obj_score,
                is_valid=is_valid,
                constraint_result=ConstraintResult(is_violated=not is_valid, details=violation_details)
            )
            trials.append(trial)
            self._repo.save_trial(run_id, trial)
            self._event_bus.publish(TrialEvaluated(payload={"trial_id": trial_id, "score": composite}))

        # 3. Compute Pareto Front solutions
        non_dominated = self._compute_pareto_front(trials)
        pareto = ParetoFront(non_dominated_trials=non_dominated)
        self._event_bus.publish(ParetoFrontUpdated(payload={"run_id": run_id, "pareto_count": len(non_dominated)}))

        # 4. Generate Robustness / Sensitivity Report
        robustness: Dict[str, RobustnessMetrics] = {}
        for param in config.space.parameters:
            metrics = RobustnessAnalyzer.evaluate_parameter(param.name, trials)
            robustness[param.name] = metrics

        # 5. Run Walk-Forward Windows
        wf_windows = WalkForwardOptimizer.generate_windows(start_time, end_time)
        self._event_bus.publish(WalkForwardCompleted(payload={"run_id": run_id}))

        best_trial = max(trials, key=lambda t: t.score.composite_score)

        opt_result = OptimizationResult(
            best_trial=best_trial,
            pareto_front=pareto,
            walk_forward_windows=wf_windows,
            robustness_report=robustness
        )

        run = OptimizationRun(
            run_id=run_id,
            configuration=config,
            status="COMPLETED",
            result=opt_result,
            timestamp=datetime.now(timezone.utc)
        )
        self._repo.save_run(run)

        self._event_bus.publish(OptimizationCompleted(payload={"run_id": run_id}))
        return opt_result

    def _compute_pareto_front(self, trials: List[OptimizationTrial]) -> List[OptimizationTrial]:
        """Filter trials to retrieve non-dominated solutions across Sharpe and CAGR."""
        valid_trials = [t for t in trials if t.is_valid]
        non_dominated = []

        for t1 in valid_trials:
            dominated = False
            for t2 in valid_trials:
                if t1.trial_id == t2.trial_id:
                    continue
                # t2 dominates t1 if t2 is strictly better in one objective and no worse in both
                t2_sharpe = t2.score.metrics.get("Sharpe", -99.0)
                t2_cagr = t2.score.metrics.get("CAGR", -99.0)
                t1_sharpe = t1.score.metrics.get("Sharpe", -99.0)
                t1_cagr = t1.score.metrics.get("CAGR", -99.0)

                if (t2_sharpe >= t1_sharpe and t2_cagr >= t1_cagr) and (t2_sharpe > t1_sharpe or t2_cagr > t1_cagr):
                    dominated = True
                    break
            if not dominated:
                non_dominated.append(t1)

        return non_dominated
