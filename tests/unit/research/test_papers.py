"""Unit tests for automated ResearchPaper generation from quantitative experiments."""

from __future__ import annotations

from datetime import datetime
from research.experiments.models import ResearchExperiment, ExperimentResult
from research.papers.generator import PaperGenerator
from research.papers.models import ResearchPaper


def test_paper_default_generation():
    """Verify that a paper is correctly compiled with default templates."""
    experiment = ResearchExperiment(
        experiment_id="exp-111",
        name="Mean Reversion Arbitrage",
        version="2.0.1",
        description="Testing Bollinger Band breakouts",
        dataset_ref="binance_ohlcv_1m",
        feature_refs=["RSI", "BollingerBands"],
        asset_universe=["BTC/USDT", "ETH/USDT"],
    )

    result = ExperimentResult(
        result_id="res-222",
        run_id="run-333",
        metrics={
            "sharpe": 2.1,
            "max_drawdown": 0.08,
            "t_statistic": 2.45,
            "p_value": 0.015,
        },
        plots={"equity_curve": "/charts/eq.png"},
        conclusion="Highly significant returns observed under ranging regime.",
    )

    paper = PaperGenerator.generate_paper(experiment=experiment, result=result)

    assert isinstance(paper, ResearchPaper)
    assert paper.experiment_id == "exp-111"
    assert paper.title == "Quantitative Analysis Report: Mean Reversion Arbitrage (v2.0.1)"
    assert "Mean Reversion Arbitrage" in paper.abstract
    assert "BTC/USDT" in paper.abstract
    assert paper.hypothesis == "Testing Bollinger Band breakouts"
    assert "RSI" in paper.features
    assert "BollingerBands" in paper.features
    assert paper.dataset == "binance_ohlcv_1m"

    # Verify statistical separation in the default generator
    # "t_statistic" has "stat" in it, so it should go to statistics
    # "p_value" doesn't have "stat" or "p_val" but let's check what generator does:
    # "statistics={k: v for k, v in result.metrics.items() if "stat" in k.lower() or "p_val" in k.lower()}"
    # Wait, "p_value" has "p_value", which doesn't contain "p_val" (it has "p_val" if we do "p_val" in "p_value", wait! Yes, "p_val" in "p_value" is True since 'p_value' contains 'p_val'!).
    assert "t_statistic" in paper.statistics
    assert "p_value" in paper.statistics
    assert "sharpe" in paper.results
    assert "max_drawdown" in paper.results

    assert "Potential overfitting on history." in paper.weaknesses
    assert "Add out-of-sample forward testing." in paper.future_work
    assert any("Hypothesis validation concluded" in lesson for lesson in paper.lessons_learned)
    assert isinstance(paper.published_at, datetime)


def test_paper_custom_generation():
    """Verify that custom title, abstract, weaknesses, and future work can be passed to generator."""
    experiment = ResearchExperiment(
        experiment_id="exp-111",
        name="Mean Reversion Arbitrage",
        description="Testing Bollinger Band breakouts",
        dataset_ref="binance_ohlcv_1m",
        asset_universe=["BTC/USDT"],
    )

    result = ExperimentResult(
        result_id="res-222",
        run_id="run-333",
        metrics={"sharpe": 2.1},
        conclusion="Good",
    )

    paper = PaperGenerator.generate_paper(
        experiment=experiment,
        result=result,
        title="Custom Title",
        abstract="Custom Abstract",
        weaknesses=["Custom Weakness"],
        future_work=["Custom Future Work"],
    )

    assert paper.title == "Custom Title"
    assert paper.abstract == "Custom Abstract"
    assert paper.weaknesses == ["Custom Weakness"]
    assert paper.future_work == ["Custom Future Work"]
