"""Unit tests for research experiments models and ExperimentManager."""

from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError

from research.experiments.models import (
    ResearchExperiment,
    ExperimentRun,
    ExperimentResult,
    ExperimentStatus,
)
from research.experiments.manager import ExperimentManager


def test_experiment_models_frozen():
    """Verify that experiment models are frozen and immutable after creation."""
    exp = ResearchExperiment(
        experiment_id="exp-123",
        name="Momentum Strategy",
        description="Hypothesis test",
        dataset_ref="ds-1",
        asset_universe=["BTC/USDT"],
    )
    with pytest.raises(ValidationError):
        # frozen model should raise validation/assignment error on modification
        exp.name = "New Name"  # type: ignore


def test_experiment_manager_creation():
    """Test creating an experiment via ExperimentManager."""
    manager = ExperimentManager()
    exp = manager.create_experiment(
        name="Mean Reversion 1h",
        description="Testing rolling Bollinger Bands z-score reversals",
        dataset_ref="binance_ohlcv_1h",
        asset_universe=["BTC/USDT", "ETH/USDT"],
        tags=["mean_reversion", "reversals"],
        feature_refs=["RSI", "ATR"],
        market_regime="ranging",
    )

    assert exp.experiment_id is not None
    assert exp.name == "Mean Reversion 1h"
    assert exp.dataset_ref == "binance_ohlcv_1h"
    assert exp.asset_universe == ["BTC/USDT", "ETH/USDT"]
    assert exp.tags == ["mean_reversion", "reversals"]
    assert exp.feature_refs == ["RSI", "ATR"]
    assert exp.market_regime == "ranging"
    assert isinstance(exp.created_at, datetime)

    # Verify retrieval
    retrieved = manager.get_experiment(exp.experiment_id)
    assert retrieved == exp


def test_experiment_manager_nonexistent_retrieved():
    """Verify retrieving a non-existent experiment returns None."""
    manager = ExperimentManager()
    assert manager.get_experiment("nonexistent") is None


def test_experiment_run_flow():
    """Test the lifecycle of a run: start -> progress/logs -> complete with success."""
    manager = ExperimentManager()
    exp = manager.create_experiment(
        name="Trend Following",
        description="EMA cross",
        dataset_ref="ds-1",
        asset_universe=["SOL/USDT"],
    )

    # Start run
    run = manager.start_run(exp.experiment_id, notes="Initial test run")
    assert run.run_id is not None
    assert run.experiment_id == exp.experiment_id
    assert run.status == ExperimentStatus.RUNNING
    assert run.notes == "Initial test run"
    assert run.logs == ["Run started"]

    # Complete run - SUCCESS
    metrics = {"sharpe": 1.75, "max_drawdown": 0.12, "p_value": 0.03}
    logs = ["Model calculated outputs", "Validation criteria met"]
    completed_run, result = manager.complete_run(
        run_id=run.run_id,
        status=ExperimentStatus.SUCCESS,
        metrics=metrics,
        logs=logs,
        conclusion="Hypothesis confirmed with good Sharpe",
    )

    assert completed_run.status == ExperimentStatus.SUCCESS
    assert completed_run.metrics == metrics
    assert "Run started" in completed_run.logs
    assert "Model calculated outputs" in completed_run.logs
    assert completed_run.completed_at is not None

    # Check result model was created and indexed
    assert result is not None
    assert result.run_id == run.run_id
    assert result.metrics == metrics
    assert result.conclusion == "Hypothesis confirmed with good Sharpe"

    # Get run and get result by run
    assert manager.get_run(run.run_id) == completed_run
    assert manager.get_result_for_run(run.run_id) == result


def test_experiment_run_flow_failed():
    """Test a failed experiment run doesn't produce an ExperimentResult."""
    manager = ExperimentManager()
    exp = manager.create_experiment(
        name="Failing Idea",
        description="Fails validation",
        dataset_ref="ds-1",
        asset_universe=["SOL/USDT"],
    )

    run = manager.start_run(exp.experiment_id)
    completed_run, result = manager.complete_run(
        run_id=run.run_id,
        status=ExperimentStatus.FAILED,
        metrics={"sharpe": -0.2},
        logs=["Drawdown exceeded threshold"],
        conclusion="Failed due to massive drawdown",
    )

    assert completed_run.status == ExperimentStatus.FAILED
    assert result is None
    assert manager.get_result_for_run(run.run_id) is None


def test_start_run_invalid_experiment():
    """Test attempting to run a nonexistent experiment raises KeyError."""
    manager = ExperimentManager()
    with pytest.raises(KeyError):
        manager.start_run("invalid-id")


def test_complete_run_invalid_run():
    """Test attempting to complete a nonexistent run raises KeyError."""
    manager = ExperimentManager()
    with pytest.raises(KeyError):
        manager.complete_run(
            run_id="invalid-run",
            status=ExperimentStatus.SUCCESS,
            metrics={},
            logs=[],
        )


def test_compare_runs():
    """Test comparing multiple runs via ExperimentManager."""
    manager = ExperimentManager()
    exp = manager.create_experiment(
        name="Compare Exp",
        description="Compare runs",
        dataset_ref="ds-1",
        asset_universe=["BTC/USDT"],
    )

    run1 = manager.start_run(exp.experiment_id)
    run1_completed, _ = manager.complete_run(run1.run_id, ExperimentStatus.SUCCESS, {"sharpe": 1.2}, [])

    run2 = manager.start_run(exp.experiment_id)
    run2_completed, _ = manager.complete_run(run2.run_id, ExperimentStatus.SUCCESS, {"sharpe": 1.8}, [])

    comparison = manager.compare_runs([run1.run_id, run2.run_id, "nonexistent"])
    assert len(comparison) == 2
    assert run1.run_id in comparison
    assert run2.run_id in comparison
    assert comparison[run1.run_id]["metrics"]["sharpe"] == 1.2
    assert comparison[run2.run_id]["metrics"]["sharpe"] == 1.8
