"""Unit tests for PortfolioOptimizer."""

from __future__ import annotations

from portfolio_construction.analysis.optimizer import PortfolioOptimizer
from portfolio_construction.core.enums import OptimizationObjective
from portfolio_construction.core.models import PortfolioCandidate, PortfolioConstraintConfig


def test_optimizer_equal_weighting():
    opt = PortfolioOptimizer()
    c1 = PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.90)
    c2 = PortfolioCandidate(signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.80)
    config = PortfolioConstraintConfig(max_weight_per_asset=0.60)

    weights = opt.optimize([c1, c2], {}, config, OptimizationObjective.EQUAL_WEIGHT)
    assert round(weights["BTC/USDT"], 2) == 0.50
    assert round(weights["ETH/USDT"], 2) == 0.50


def test_optimizer_confidence_weighting():
    opt = PortfolioOptimizer()
    c1 = PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.80)
    c2 = PortfolioCandidate(signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.20)
    config = PortfolioConstraintConfig(max_weight_per_asset=0.90)

    weights = opt.optimize([c1, c2], {}, config, OptimizationObjective.CONFIDENCE_WEIGHTED)
    assert weights["BTC/USDT"] > weights["ETH/USDT"]
    assert weights["BTC/USDT"] <= 0.90


def test_optimizer_applies_weight_caps():
    opt = PortfolioOptimizer()
    c1 = PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.90)
    c2 = PortfolioCandidate(signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.10)
    config = PortfolioConstraintConfig(max_weight_per_asset=0.40)

    weights = opt.optimize([c1, c2], {}, config, OptimizationObjective.CONFIDENCE_WEIGHTED)
    for sym, w in weights.items():
        assert w <= 0.40
