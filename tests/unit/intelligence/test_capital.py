"""Unit tests for the Capital Allocator."""

from __future__ import annotations

import pytest
from intelligence.capital.allocator import CapitalAllocator


@pytest.fixture
def allocator() -> CapitalAllocator:
    """Provide a CapitalAllocator instance."""
    return CapitalAllocator(
        fractional_kelly=0.5,  # Half Kelly
        max_portfolio_exposure=0.70,  # 70% max exposure
        default_payoff_ratio=2.0,
    )


def test_calculate_kelly_fraction(allocator: CapitalAllocator) -> None:
    """Test standard Kelly sizing outputs."""
    # win_rate=0.6, payoff=2.0 -> f = 0.6 - 0.4/2.0 = 0.6 - 0.2 = 0.40
    assert pytest.approx(allocator.calculate_kelly_fraction(0.6, 2.0), 0.001) == 0.40

    # Negative edge case payoff or negative expectancy
    assert allocator.calculate_kelly_fraction(0.3, 2.0) == 0.0
    assert allocator.calculate_kelly_fraction(0.6, -1.0) == 0.0


def test_suggest_sizing(allocator: CapitalAllocator) -> None:
    """Test single asset allocation sugerence with caps and scaling."""
    # win_rate=0.6, payoff=2.0 -> Kelly=0.40
    # half Kelly = 0.20
    # confidence=0.8 -> target = 0.16
    # risk_budget_pct = 0.10 -> capped to 10%
    suggestion = allocator.suggest_sizing(
        symbol="BTC/USDT",
        win_rate=0.6,
        payoff_ratio=2.0,
        confidence=0.8,
        portfolio_value=100000.0,
        risk_budget_pct=0.10,
    )

    assert suggestion.symbol == "BTC/USDT"
    assert suggestion.target_percentage == 0.10
    assert suggestion.suggested_amount == 10000.0
    assert suggestion.is_capped is True

    # Check non-capped
    suggestion_uncapped = allocator.suggest_sizing(
        symbol="BTC/USDT",
        win_rate=0.55,
        payoff_ratio=2.0,
        confidence=0.5,
        portfolio_value=100000.0,
        risk_budget_pct=0.10,
    )
    # Kelly = 0.55 - 0.45/2.0 = 0.325
    # scaled = 0.325 * 0.5 * 0.5 = 0.08125
    assert pytest.approx(suggestion_uncapped.target_percentage, 0.0001) == 0.08125
    assert suggestion_uncapped.is_capped is False


def test_suggest_portfolio_allocations(allocator: CapitalAllocator) -> None:
    """Test multi-asset portfolio sizing recommendations with scale constraints and correlation adjustments."""
    opps = [
        {"symbol": "BTC/USDT", "win_rate": 0.6, "payoff_ratio": 2.0, "confidence": 0.8, "risk_budget_pct": 0.10},
        {"symbol": "ETH/USDT", "win_rate": 0.6, "payoff_ratio": 2.0, "confidence": 0.8, "risk_budget_pct": 0.10},
    ]

    # Without correlations
    suggestions = allocator.suggest_portfolio_allocations(
        opportunities=opps,
        portfolio_value=100000.0,
        cash_available=50000.0,  # Limits max exposure to 50k / 100k = 50%
    )

    assert len(suggestions) == 2
    # Each raw scaled size is 0.10 (capped)
    # Sum of raw sizes is 20% (0.20).
    # Since 20% is <= max cash exposure of 50%, no proportional scale-down is required!
    assert suggestions[0].target_percentage == 0.10
    assert suggestions[1].target_percentage == 0.10

    # Test scale-down limit
    suggestions_scaled = allocator.suggest_portfolio_allocations(
        opportunities=opps,
        portfolio_value=100000.0,
        cash_available=15000.0,  # 15% limit. Sum 20% must scale down to 15% (0.75x factor)
    )
    assert suggestions_scaled[0].target_percentage == 0.075
    assert suggestions_scaled[1].target_percentage == 0.075

    # Test correlation penalty
    # Correlated assets should see sizing scaled down
    suggestions_corr = allocator.suggest_portfolio_allocations(
        opportunities=opps,
        portfolio_value=100000.0,
        cash_available=50000.0,
        correlations={("BTC/USDT", "ETH/USDT"): 0.8},
    )
    # Penalty factor: 1.0 - 0.5 * 0.8 = 0.6x
    # target = 0.10 * 0.6 = 0.06
    assert pytest.approx(suggestions_corr[0].target_percentage, 0.001) == 0.06
    assert pytest.approx(suggestions_corr[1].target_percentage, 0.001) == 0.06
