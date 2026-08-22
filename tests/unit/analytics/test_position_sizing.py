"""Unit tests for the PositionSizer position sizing engines."""

from __future__ import annotations

import pytest

from analytics.position_sizing.sizing import PositionSizer


def test_kelly_sizing():
    """Verify Kelly-based fraction scaling."""
    # Win rate 55%, win-loss 2:1. Kelly = 0.55 - (1 - 0.55)/2 = 0.55 - 0.225 = 0.325
    k = PositionSizer.kelly_sizing(win_rate=0.55, win_loss_ratio=2.0, leverage_fraction=1.0)
    assert pytest.approx(k) == 0.325
    
    # Leveraged Kelly
    k_half = PositionSizer.kelly_sizing(win_rate=0.55, win_loss_ratio=2.0, leverage_fraction=0.5)
    assert pytest.approx(k_half) == 0.1625


def test_volatility_adjusted_sizing():
    """Verify volatility risk-adjusted share quantities."""
    # Equity = 100000, target risk = 1% (1000), asset vol = 20% (0.2), price = 100.
    # Qty = 1000 / (0.2 * 100) = 1000 / 20 = 50.0
    qty = PositionSizer.volatility_adjusted_sizing(
        total_equity=100000.0,
        target_risk_pct=0.01,
        asset_volatility=0.2,
        price=100.0,
    )
    assert qty == 50.0
    
    # Boundary checks
    assert PositionSizer.volatility_adjusted_sizing(1000.0, 0.01, 0.0, 100.0) == 0.0


def test_equal_risk_sizing():
    """Verify stop-loss equal risk share sizing."""
    # Equity = 10000, target risk = 2% (200), stop loss distance = 5.0 absolute.
    # Qty = 200 / 5.0 = 40.0
    qty = PositionSizer.equal_risk_sizing(
        total_equity=10000.0,
        target_risk_pct=0.02,
        stop_loss_distance=5.0,
    )
    assert qty == 40.0
    
    # Boundary checks
    assert PositionSizer.equal_risk_sizing(1000.0, 0.02, 0.0) == 0.0


def test_fixed_fractional_sizing():
    """Verify fixed cash fraction asset allocation."""
    # Equity = 10000, allocation fraction = 10% (1000), price = 50.0.
    # Qty = 1000 / 50.0 = 20.0
    qty = PositionSizer.fixed_fractional_sizing(
        total_equity=10000.0,
        fraction=0.10,
        price=50.0,
    )
    assert qty == 20.0
