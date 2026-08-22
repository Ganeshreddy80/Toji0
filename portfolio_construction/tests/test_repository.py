"""Unit tests for PortfolioConstructionRepository."""

from __future__ import annotations

from portfolio_construction.core.enums import PortfolioDecision
from portfolio_construction.core.models import (
    PortfolioConstructionSnapshot,
    PortfolioConstructionState,
    TargetPortfolio,
)
from portfolio_construction.core.repository import PortfolioConstructionRepository


def test_repository_save_and_load_snapshot():
    repo = PortfolioConstructionRepository()
    target = TargetPortfolio(
        decision=PortfolioDecision.REBALANCE,
        allocations={},
        target_weights={"BTC/USDT": 0.50},
        total_weight=0.50,
        active_positions_count=1,
        confidence=0.90,
        reasoning="Test portfolio",
    )
    state = PortfolioConstructionState(symbol="PORTFOLIO", active_portfolio=target)
    snap = PortfolioConstructionSnapshot(snapshot_id="snap-100", state=state)

    repo.save_snapshot(snap)

    loaded = repo.load_latest_snapshot("PORTFOLIO")
    assert loaded is not None
    assert loaded.snapshot_id == "snap-100"
    assert loaded.state.active_portfolio.target_weights == {"BTC/USDT": 0.50}


def test_repository_save_and_load_correlation_matrix():
    repo = PortfolioConstructionRepository()
    matrix = {
        "BTC/USDT": {"ETH/USDT": 0.80},
        "ETH/USDT": {"BTC/USDT": 0.80},
    }
    repo.save_correlation_matrix("PORTFOLIO", matrix)

    loaded = repo.get_correlation_matrix("PORTFOLIO")
    assert loaded == matrix
