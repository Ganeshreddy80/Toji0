"""Unit tests for the strategy parameter optimization and sensitivity engines."""

from __future__ import annotations

from typing import Any
import pytest

from analytics.optimization.search import GridSearch, RandomSearch
from analytics.optimization.sensitivity import SensitivityAnalyzer


# Simple mock runner class that evaluates performance based on parameters
class DummyStrategyRunner:
    def __init__(self, parameters: dict[str, Any]) -> None:
        self.parameters = parameters


def mock_runner_factory(params: dict[str, Any]) -> DummyStrategyRunner:
    return DummyStrategyRunner(params)


def mock_metric_evaluator(runner: DummyStrategyRunner) -> float:
    # Let's say Sharpe is maximized when MA is 50
    ma = runner.parameters.get("ma", 50)
    return float(2.0 - abs(ma - 50) * 0.1)


def test_grid_search():
    """Verify GridSearch evaluates all combinations and sorts the best first."""
    param_grid = {
        "ma": [30, 40, 50, 60],
        "leverage": [1.0, 2.0],
    }
    
    results = GridSearch.optimize(
        runner_factory=mock_runner_factory,
        parameter_grid=param_grid,
        metric_evaluator=mock_metric_evaluator,
    )
    
    # 4 (ma) * 2 (leverage) = 8 combinations
    assert len(results) == 8
    # Best combination should have ma=50, metric_value = 2.0
    assert results[0]["parameters"]["ma"] == 50
    assert results[0]["metric_value"] == 2.0
    # Results must be sorted in descending order of metric_value
    assert results[0]["metric_value"] >= results[-1]["metric_value"]


def test_random_search():
    """Verify RandomSearch samples combinations coordinate points from parameter grid."""
    param_grid = {
        "ma": list(range(10, 100)),
        "leverage": [1.0, 2.0],
    }
    
    results = RandomSearch.optimize(
        runner_factory=mock_runner_factory,
        parameter_grid=param_grid,
        metric_evaluator=mock_metric_evaluator,
        n_iterations=5,
    )
    
    assert len(results) == 5
    assert results[0]["metric_value"] >= results[-1]["metric_value"]


def test_sensitivity_analyzer():
    """Verify SensitivityAnalyzer perturbs parameter settings individually."""
    base_params = {"ma": 50, "leverage": 1.0}
    perturbations = {"ma": [40, 60], "leverage": [1.5]}
    
    report = SensitivityAnalyzer.analyze_sensitivity(
        runner_factory=mock_runner_factory,
        base_parameters=base_params,
        perturbations=perturbations,
        metric_evaluator=mock_metric_evaluator,
    )
    
    assert "ma" in report
    assert "leverage" in report
    
    # Baseline for ma was 50 (metric value = 2.0)
    assert report["ma"]["50"] == 2.0
    # Perturbation value 40 should have metric value = 2.0 - 1.0 = 1.0
    assert report["ma"]["40"] == 1.0
    assert report["ma"]["60"] == 1.0
