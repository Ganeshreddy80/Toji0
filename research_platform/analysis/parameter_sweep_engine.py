"""Parameter sweep optimization engine for the Research Platform (Sprint 6)."""

from __future__ import annotations

from datetime import datetime, timezone
import itertools
import logging
import random
from typing import Any, Callable, Dict, List

from research_platform.core.enums import SweepMethod
from research_platform.core.exceptions import ParameterSweepError
from research_platform.core.interfaces import IParameterSweepEngine
from research_platform.core.models import (
    ParameterSweepConfig,
    ParameterSweepResult,
    ParameterSweepTrial,
    PerformanceMetrics,
)

logger = logging.getLogger(__name__)


class ParameterSweepEngine(IParameterSweepEngine):
    """Executes deterministic parameter sweep optimization across strategy parameter ranges."""

    def run_sweep(
        self,
        eval_fn: Callable[[Dict[str, Any]], PerformanceMetrics],
        config: ParameterSweepConfig,
    ) -> ParameterSweepResult:
        """Execute parameter sweep evaluation across candidate parameter combinations."""
        if not config or not config.parameter_ranges:
            raise ParameterSweepError("ParameterSweepConfig must contain non-empty parameter_ranges.")

        param_names = list(config.parameter_ranges.keys())
        param_value_lists = [config.parameter_ranges[k] for k in param_names]

        # Generate candidate parameter dictionaries
        if config.method == SweepMethod.GRID:
            combinations = [
                dict(zip(param_names, combination))
                for combination in itertools.product(*param_value_lists)
            ]
            if len(combinations) > config.max_iterations:
                combinations = combinations[: config.max_iterations]
        else:
            # Seeded Random / Bayesian sampling for determinism
            rng = random.Random(config.seed)
            combinations = []
            all_combos = [
                dict(zip(param_names, combination))
                for combination in itertools.product(*param_value_lists)
            ]
            if len(all_combos) <= config.max_iterations:
                combinations = all_combos
            else:
                combinations = rng.sample(all_combos, config.max_iterations)

        sweep_id = config.sweep_id or ParameterSweepConfig.generate_sweep_id(config.parameter_ranges, seed=config.seed)

        trials: List[ParameterSweepTrial] = []
        for idx, params in enumerate(combinations, start=1):
            trial_id = f"trial-{sweep_id[:8]}-{idx}"
            try:
                metrics = eval_fn(params)
            except Exception as e:
                logger.error("ParameterSweepEngine: Trial %s failed: %s", trial_id, e)
                metrics = PerformanceMetrics()

            trial = ParameterSweepTrial(
                trial_id=trial_id,
                parameters=params,
                metrics=metrics,
                rank=idx,
            )
            trials.append(trial)

        # Sort trials by Sharpe ratio descending
        trials.sort(key=lambda t: t.metrics.sharpe_ratio, reverse=True)

        # Update ranks after sorting
        ranked_trials: List[ParameterSweepTrial] = []
        for r, trial in enumerate(trials, start=1):
            ranked_trials.append(trial.model_copy(update={"rank": r}))

        best_trial = ranked_trials[0] if ranked_trials else ParameterSweepTrial(trial_id="empty", parameters={}, metrics=PerformanceMetrics(), rank=1)

        return ParameterSweepResult(
            sweep_id=sweep_id,
            best_parameters=best_trial.parameters,
            best_metrics=best_trial.metrics,
            trials=ranked_trials,
            completed_at=datetime.now(timezone.utc),
        )
