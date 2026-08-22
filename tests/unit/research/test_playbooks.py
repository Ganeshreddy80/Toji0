"""Unit tests for quantitative research playbooks."""

from __future__ import annotations

from research.experiments.manager import ExperimentManager
from research.experiments.models import ResearchExperiment
from research.playbooks.implementations import (
    MomentumResearchPlaybook,
    MeanReversionResearchPlaybook,
    BreakoutResearchPlaybook,
    MacroResearchPlaybook,
    FactorResearchPlaybook,
)


def test_momentum_playbook():
    """Verify momentum research playbook properties and execute workflow."""
    manager = ExperimentManager()
    playbook = MomentumResearchPlaybook()

    assert playbook.name == "Momentum Research"
    assert "rolling trend" in playbook.description
    assert playbook.required_datasets == ["ohlcv_history"]
    assert "EMA" in playbook.required_features
    assert "RSI" in playbook.required_features
    assert len(playbook.steps) == 4
    assert playbook.validation_criteria["min_sharpe"] == 1.5

    # Execute
    exp = playbook.execute(
        manager=manager,
        dataset_ref="test_dataset_1d",
        asset_universe=["BTC/USDT", "ETH/USDT"],
        custom_inputs={"market_regime": "trending"},
    )

    assert isinstance(exp, ResearchExperiment)
    assert exp.name == "Momentum Research Run"
    assert exp.dataset_ref == "test_dataset_1d"
    assert exp.asset_universe == ["BTC/USDT", "ETH/USDT"]
    assert exp.market_regime == "trending"
    assert "momentum_research" in exp.tags
    assert "playbook_derived" in exp.tags
    assert exp.feature_refs == ["EMA", "RSI", "MACD", "Momentum"]

    # Verify registration in manager
    assert manager.get_experiment(exp.experiment_id) == exp


def test_mean_reversion_playbook():
    """Verify mean reversion research playbook properties and execution."""
    manager = ExperimentManager()
    playbook = MeanReversionResearchPlaybook()

    assert playbook.name == "Mean Reversion Research"
    assert playbook.required_datasets == ["ohlcv_history"]
    assert "Volatility" in playbook.required_features
    assert playbook.validation_criteria["min_sharpe"] == 1.8

    exp = playbook.execute(
        manager=manager,
        dataset_ref="test_dataset_5m",
        asset_universe=["BTC/USDT"],
        custom_inputs={"market_regime": "ranging"},
    )
    assert exp.market_regime == "ranging"
    assert "mean_reversion_research" in exp.tags
    assert exp.feature_refs == ["RSI", "ATR", "Volatility"]


def test_breakout_playbook():
    """Verify breakout research playbook properties and execution."""
    manager = ExperimentManager()
    playbook = BreakoutResearchPlaybook()

    assert playbook.name == "Breakout Research"
    assert playbook.required_datasets == ["ohlcv_history", "orderbook_depth"]
    assert "VWAP" in playbook.required_features
    assert playbook.validation_criteria["max_drawdown"] == 0.20

    exp = playbook.execute(
        manager=manager,
        dataset_ref="test_dataset_1h",
        asset_universe=["SOL/USDT"],
        custom_inputs={},
    )
    assert exp.market_regime is None
    assert "breakout_research" in exp.tags
    assert exp.feature_refs == ["ATR", "VWAP", "VolumeProfile", "Liquidity"]


def test_macro_playbook():
    """Verify macro research playbook properties and execution."""
    manager = ExperimentManager()
    playbook = MacroResearchPlaybook()

    assert playbook.name == "Macro Research"
    assert playbook.required_datasets == ["macro_calendar"]
    assert "Funding" in playbook.required_features
    assert playbook.validation_criteria["min_win_rate"] == 0.55

    exp = playbook.execute(
        manager=manager,
        dataset_ref="macro_calendar_feed",
        asset_universe=["BTC/USDT", "ETH/USDT"],
        custom_inputs={"market_regime": "high_vol"},
    )
    assert exp.market_regime == "high_vol"
    assert "macro_research" in exp.tags
    assert exp.feature_refs == ["Funding", "Volatility"]


def test_factor_playbook():
    """Verify factor research playbook properties and execution."""
    manager = ExperimentManager()
    playbook = FactorResearchPlaybook()

    assert playbook.name == "Factor Research"
    assert playbook.required_datasets == ["ohlcv_history"]
    assert "VWAP" in playbook.required_features
    assert playbook.validation_criteria["min_t_stat"] == 2.0

    exp = playbook.execute(
        manager=manager,
        dataset_ref="ohlcv_15m",
        asset_universe=["UNI/USDT", "LINK/USDT"],
        custom_inputs={},
    )
    assert "factor_research" in exp.tags
    assert exp.feature_refs == ["EMA", "RSI", "ATR", "VWAP"]
