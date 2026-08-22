"""Unit tests for CorrelationFilter."""

from __future__ import annotations

from portfolio_construction.analysis.correlation_filter import CorrelationFilter
from portfolio_construction.core.models import PortfolioCandidate


def test_correlation_filter_rejects_correlated_assets():
    filter_engine = CorrelationFilter()
    c1 = PortfolioCandidate(
        signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Trend Following", confidence=0.90
    )
    c2 = PortfolioCandidate(
        signal_id="s2", symbol="ETH/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Breakout", confidence=0.85
    )

    # Correlation between BTC and ETH is 0.85 (> max_correlation 0.70)
    matrix = {
        "BTC/USDT": {"ETH/USDT": 0.85},
        "ETH/USDT": {"BTC/USDT": 0.85},
    }

    accepted, rejected = filter_engine.filter_candidates(
        candidates=[c1, c2],
        correlation_matrix=matrix,
        max_correlation=0.70,
    )

    # c1 (BTC) has higher confidence (0.90 vs 0.85) -> accepted
    # c2 (ETH) is rejected
    assert len(accepted) == 1
    assert accepted[0].symbol == "BTC/USDT"
    assert rejected == ["ETH/USDT"]


def test_correlation_filter_accepts_uncorrelated_assets():
    filter_engine = CorrelationFilter()
    c1 = PortfolioCandidate(
        signal_id="s1", symbol="BTC/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Trend Following", confidence=0.90
    )
    c2 = PortfolioCandidate(
        signal_id="s2", symbol="SOL/USDT", timeframe="1h", direction="BULLISH",
        strategy_type="Breakout", confidence=0.85
    )

    matrix = {
        "BTC/USDT": {"SOL/USDT": 0.30},
        "SOL/USDT": {"BTC/USDT": 0.30},
    }

    accepted, rejected = filter_engine.filter_candidates(
        candidates=[c1, c2],
        correlation_matrix=matrix,
        max_correlation=0.70,
    )

    assert len(accepted) == 2
    assert rejected == []
