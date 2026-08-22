"""Grid search, random search, and interface definitions for strategy parameters optimization."""

from __future__ import annotations

import abc
import itertools
import random
from typing import Any, Callable


class IBayesianOptimizer(abc.ABC):
    """Abstract interface contract for pluggable Bayesian search engines (e.g. Optuna)."""

    @abc.abstractmethod
    def optimize(
        self,
        objective_func: Callable[[dict[str, Any]], float],
        parameter_bounds: dict[str, tuple[Any, Any]],
        n_trials: int = 50,
    ) -> dict[str, Any]:
        """Run Bayesian optimization search trials to maximize the objective function."""


class GridSearch:
    """Exhaustive parameter sweep optimization search engine."""

    @staticmethod
    def optimize(
        runner_factory: Callable[[dict[str, Any]], Any],
        parameter_grid: dict[str, list[Any]],
        metric_evaluator: Callable[[Any], float],
    ) -> list[dict[str, Any]]:
        """Run grid search over the Cartesian product of the parameter grid."""
        keys, values = zip(*parameter_grid.items())
        experiments = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        results = []
        for params in experiments:
            runner = runner_factory(params)
            metric_val = metric_evaluator(runner)
            results.append({
                "parameters": params,
                "metric_value": metric_val
            })
            
        # Sort best first
        return sorted(results, key=lambda x: x["metric_value"], reverse=True)


class RandomSearch:
    """Randomized parameter sampling optimization search engine."""

    @staticmethod
    def optimize(
        runner_factory: Callable[[dict[str, Any]], Any],
        parameter_grid: dict[str, list[Any]],
        metric_evaluator: Callable[[Any], float],
        n_iterations: int = 10,
    ) -> list[dict[str, Any]]:
        """Run random search by randomly sampling combination coordinates from the grid."""
        keys, values = zip(*parameter_grid.items())
        all_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        n_samples = min(n_iterations, len(all_combinations))
        sampled_combinations = random.sample(all_combinations, n_samples)
        
        results = []
        for params in sampled_combinations:
            runner = runner_factory(params)
            metric_val = metric_evaluator(runner)
            results.append({
                "parameters": params,
                "metric_value": metric_val
            })
            
        return sorted(results, key=lambda x: x["metric_value"], reverse=True)
