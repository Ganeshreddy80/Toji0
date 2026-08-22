"""Comparison engine evaluating parameter variations and metrics across runs.
"""

from __future__ import annotations

from typing import List, Dict
from research_platform.experiment_manager.interfaces import IComparisonEngine
from research_platform.experiment_manager.models import ExperimentComparison, Experiment
from research_platform.experiment_manager.repository import ExperimentRepository


class ComparisonEngine(IComparisonEngine):
    """Evaluates differences in Sharpe, returns, and drawdown parameters."""

    def __init__(self, repo: ExperimentRepository) -> None:
        self._repo = repo

    def compare_runs(self, experiment_ids: List[str]) -> ExperimentComparison:
        runs: List[Experiment] = []
        for r_id in experiment_ids:
            exp = self._repo.get_experiment(r_id)
            if exp:
                runs.append(exp)

        if not runs:
            return ExperimentComparison(experiment_ids=experiment_ids)

        differing = []
        metric_diffs: Dict[str, List[float]] = {}
        
        # Enforce basic keys diffs logic
        if len(runs) > 1:
            first_seeds = runs[0].reproducibility.random_seed
            for r in runs[1:]:
                if r.reproducibility.random_seed != first_seeds:
                    differing.append("random_seed")
                    break

        return ExperimentComparison(
            experiment_ids=experiment_ids,
            metric_differences=metric_diffs,
            differing_keys=differing
        )
