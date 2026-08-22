"""Unit tests for PortfolioConstraintEngine."""

from __future__ import annotations

from portfolio_construction.analysis.constraint_engine import PortfolioConstraintEngine
from portfolio_construction.core.models import PortfolioCandidate, PortfolioConstraintConfig


def test_constraint_engine_validates_valid_portfolio():
    ce = PortfolioConstraintEngine()
    c1 = PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.85, sector="CURRENCIES")
    c2 = PortfolioCandidate(signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.80, sector="PLATFORMS")
    config = PortfolioConstraintConfig()

    weights = {"BTC/USDT": 0.40, "ETH/USDT": 0.30}
    is_valid, violations = ce.validate_constraints([c1, c2], weights, config)

    assert is_valid is True
    assert violations == []


def test_constraint_engine_detects_max_weight_violation():
    ce = PortfolioConstraintEngine()
    c1 = PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.85)
    config = PortfolioConstraintConfig(max_weight_per_asset=0.40)

    weights = {"BTC/USDT": 0.60}  # 0.60 > 0.40 cap
    is_valid, violations = ce.validate_constraints([c1], weights, config)

    assert is_valid is False
    assert any("max_weight_per_asset" in v for v in violations)


def test_constraint_engine_detects_total_weight_overcap():
    ce = PortfolioConstraintEngine()
    c1 = PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.85)
    c2 = PortfolioCandidate(signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.80)
    c3 = PortfolioCandidate(signal_id="s3", symbol="SOL/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.75)
    config = PortfolioConstraintConfig(max_weight_per_asset=0.50)

    weights = {"BTC/USDT": 0.45, "ETH/USDT": 0.45, "SOL/USDT": 0.30}  # sum = 1.20 > 1.0
    is_valid, violations = ce.validate_constraints([c1, c2, c3], weights, config)

    assert is_valid is False
    assert any("exceeds 1.0 cap" in v for v in violations)
