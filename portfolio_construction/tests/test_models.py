"""Unit tests for Portfolio Construction Engine models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from portfolio_construction.core.enums import PortfolioDecision
from portfolio_construction.core.models import (
    PortfolioCandidate,
    PortfolioConstraintConfig,
    TargetAllocation,
    TargetPortfolio,
    PortfolioConstructionState,
    PortfolioConstructionSnapshot,
)


def test_portfolio_candidate_validation_and_normalization():
    cand = PortfolioCandidate(
        signal_id="sig-001",
        symbol="BTC/USDT",
        timeframe="1h",
        direction="BULLISH",
        strategy_type="Trend Following",
        confidence=85.0,  # Auto normalized from percentage
        sector="CRYPTO",
    )
    assert cand.confidence == 0.85
    assert cand.symbol == "BTC/USDT"
    assert cand.sector == "CRYPTO"

    with pytest.raises(ValidationError):
        cand.confidence = 0.50  # Frozen instance mutation error


def test_target_portfolio_immutability():
    alloc = TargetAllocation(
        symbol="BTC/USDT",
        target_weight=0.35,
        confidence=0.90,
        strategy_type="Trend Following",
        reasoning="Strong trend setup",
    )
    target = TargetPortfolio(
        decision=PortfolioDecision.REBALANCE,
        allocations={"BTC/USDT": alloc},
        target_weights={"BTC/USDT": 0.35},
        total_weight=0.35,
        active_positions_count=1,
        confidence=0.90,
        reasoning="Constructed 1 position",
    )
    assert target.decision == PortfolioDecision.REBALANCE
    assert target.total_weight == 0.35

    with pytest.raises(ValidationError):
        target.confidence = 0.50


def test_portfolio_constraint_config_defaults():
    config = PortfolioConstraintConfig()
    assert config.max_correlation == 0.70
    assert config.max_weight_per_asset == 0.40
    assert config.min_weight_per_asset == 0.05
    assert config.max_positions == 10
    assert config.max_sector_exposure == 0.50
