"""Unit tests for research knowledge entries, alpha factors, and report generation."""

from __future__ import annotations

import pytest
from datetime import datetime
from pydantic import ValidationError

from research.alpha import AlphaFactor
from research.knowledge.models import KnowledgeEntry
from research.reports import ReportGenerator
from research.experiments.models import ExperimentRun, ExperimentStatus
from research.strategies.models import Strategy
from research.validation.interfaces import ValidationResult


def test_knowledge_entry_instantiation():
    """Verify KnowledgeEntry can be created and is immutable."""
    entry = KnowledgeEntry(
        entry_id="ke-123",
        experiment_id="exp-456",
        title="EMA crossover works in bull markets",
        concept="Momentum indicator confirmation",
        evidence="t-stat of 2.45, p-value < 0.05",
        is_lessons_learned=False,
    )

    assert entry.entry_id == "ke-123"
    assert entry.experiment_id == "exp-456"
    assert entry.is_lessons_learned is False
    assert isinstance(entry.created_at, datetime)

    with pytest.raises(ValidationError):
        entry.title = "New Title"  # type: ignore


def test_alpha_factor_instantiation():
    """Verify AlphaFactor model properties and validation."""
    factor = AlphaFactor(
        factor_id="af-99",
        name="Mean Reversion 5m",
        formula_expr="(close - sma) / std",
        expected_regime="ranging",
        ic_score=0.15,
        t_stat=2.1,
    )

    assert factor.factor_id == "af-99"
    assert factor.name == "Mean Reversion 5m"
    assert factor.ic_score == 0.15
    assert factor.t_stat == 2.1

    with pytest.raises(ValidationError):
        # ic_score must be between -1.0 and 1.0
        AlphaFactor(
            factor_id="af-err",
            name="Err",
            formula_expr="err",
            expected_regime="ranging",
            ic_score=2.5,
        )


def test_report_generator_summary():
    """Test ReportGenerator.generate_summary with a mix of entries."""
    entries = [
        KnowledgeEntry(
            entry_id="ke-1",
            experiment_id="exp-1",
            title="Succeeded",
            concept="C1",
            evidence="E1",
            is_lessons_learned=False,
        ),
        KnowledgeEntry(
            entry_id="ke-2",
            experiment_id="exp-2",
            title="Failed",
            concept="C2",
            evidence="E2",
            is_lessons_learned=True,
        ),
    ]

    summary = ReportGenerator.generate_summary(experiments_count=5, knowledge_entries=entries)
    assert summary["report_type"] == "Research Summary"
    assert summary["metrics"]["total_experiments"] == 5
    assert summary["metrics"]["alpha_learnings"] == 1
    assert summary["metrics"]["risk_lessons"] == 1


def test_report_generator_compare_experiments():
    """Test ReportGenerator.compare_experiments compares metrics of multiple runs."""
    run1 = ExperimentRun(
        run_id="run-1",
        experiment_id="exp-1",
        status=ExperimentStatus.SUCCESS,
        metrics={"sharpe": 1.2},
    )
    run2 = ExperimentRun(
        run_id="run-2",
        experiment_id="exp-1",
        status=ExperimentStatus.FAILED,
        metrics={"sharpe": -0.5},
    )

    report = ReportGenerator.compare_experiments([run1, run2])
    assert report["report_type"] == "Experiment Comparison"
    assert "run-1" in report["comparison"]
    assert "run-2" in report["comparison"]
    assert report["comparison"]["run-1"]["metrics"]["sharpe"] == 1.2
    assert report["comparison"]["run-2"]["status"] == "failed"


def test_report_generator_compare_strategies():
    """Test ReportGenerator.compare_strategies metadata collation."""
    strat = Strategy(
        strategy_id="strat-1",
        name="EMA Cross",
        experiment_id="exp-1",
        metadata={"author": "Team"},
    )
    report = ReportGenerator.compare_strategies([strat])
    assert report["report_type"] == "Strategy Comparison"
    assert "strat-1" in report["comparison"]
    assert report["comparison"]["strat-1"]["name"] == "EMA Cross"
    assert report["comparison"]["strat-1"]["metadata"]["author"] == "Team"


def test_report_generator_optimization():
    """Test ReportGenerator.generate_optimization_report parameter sweep sorting."""
    sweep = [
        {"parameters": {"ema": 20}, "sharpe": 1.1},
        {"parameters": {"ema": 50}, "sharpe": 1.8},
        {"parameters": {"ema": 100}, "sharpe": 1.3},
    ]

    report = ReportGenerator.generate_optimization_report(sweep, metrics_key="sharpe")
    assert report["report_type"] == "Optimization Report"
    assert report["best_parameters"] == {"ema": 50}
    assert report["best_metric"] == 1.8
    assert report["total_sweeps"] == 3

    # Empty sweep handling
    empty_report = ReportGenerator.generate_optimization_report([])
    assert empty_report["best_metric"] == 0.0


def test_report_generator_validation_report():
    """Test ReportGenerator.generate_validation_report aggregates validation outputs."""
    results = [
        ValidationResult(passed=True, metrics={"sharpe": 1.5}),
        ValidationResult(passed=False, metrics={"sharpe": 0.8}),
    ]

    report = ReportGenerator.generate_validation_report(results)
    assert report["report_type"] == "Validation Report"
    assert report["passed_checks"] == 1
    assert report["total_checks"] == 2
    assert report["passed_ratio"] == 0.5
    assert len(report["results"]) == 2
