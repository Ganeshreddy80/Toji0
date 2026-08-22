"""Unit tests for DiversificationEngine."""

from __future__ import annotations

from portfolio_construction.analysis.diversification_engine import DiversificationEngine
from portfolio_construction.core.models import PortfolioCandidate, PortfolioConstraintConfig


def test_diversification_engine_enforces_max_positions():
    div_engine = DiversificationEngine()
    candidates = [
        PortfolioCandidate(signal_id=f"s{i}", symbol=f"SYM{i}/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.90 - i * 0.05)
        for i in range(5)
    ]
    config = PortfolioConstraintConfig(max_positions=3)

    accepted, rejected = div_engine.apply_diversification(candidates, config)
    assert len(accepted) == 3
    assert len(rejected) == 2
    assert [c.symbol for c in accepted] == ["SYM0/USDT", "SYM1/USDT", "SYM2/USDT"]
    assert rejected == ["SYM3/USDT", "SYM4/USDT"]


def test_diversification_engine_enforces_sector_caps():
    div_engine = DiversificationEngine()
    candidates = [
        PortfolioCandidate(signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.90, sector="DEFI"),
        PortfolioCandidate(signal_id="s2", symbol="UNI/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.85, sector="DEFI"),
        PortfolioCandidate(signal_id="s3", symbol="AAVE/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.80, sector="DEFI"),
        PortfolioCandidate(signal_id="s4", symbol="SOL/USDT", timeframe="1h", direction="BULLISH", strategy_type="Trend", confidence=0.75, sector="L1"),
    ]
    # Sector limit max 0.30 -> caps sector count
    config = PortfolioConstraintConfig(max_positions=10, max_sector_exposure=0.10, min_weight_per_asset=0.08)

    accepted, rejected = div_engine.apply_diversification(candidates, config)
    # Only 1 candidate from DEFI should be accepted before exposure cap exceeded
    defi_accepted = [c for c in accepted if c.sector == "DEFI"]
    assert len(defi_accepted) == 1
    assert "UNI/USDT" in rejected or "AAVE/USDT" in rejected
