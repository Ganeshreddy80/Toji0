"""Unit tests for the Asset Health Calculator."""

from __future__ import annotations

import pytest
from intelligence.asset_health.calculator import AssetHealthCalculator


@pytest.fixture
def calculator() -> AssetHealthCalculator:
    """Provide a fresh AssetHealthCalculator instance."""
    return AssetHealthCalculator(
        volume_baseline=1000.0,
        spread_baseline=0.001,
        volatility_baseline=0.01,
    )


def test_calculate_volatility(calculator: AssetHealthCalculator) -> None:
    """Test volatility returns calculations."""
    prices = [100.0, 101.0, 100.0, 99.0, 100.0]
    vol = calculator.calculate_volatility(prices)
    assert vol > 0.0
    assert calculator.calculate_volatility([100.0]) == 0.0


def test_calculate_manipulation_risk(calculator: AssetHealthCalculator) -> None:
    """Test manipulation risk factors under high/low volume and spread setups."""
    # Low volume, high spread, high volatility -> High risk
    high_risk = calculator.calculate_manipulation_risk(
        avg_volume=10.0,
        avg_spread=0.05,
        volatility=0.08,
    )

    # High volume, low spread, low volatility -> Low risk
    low_risk = calculator.calculate_manipulation_risk(
        avg_volume=100000.0,
        avg_spread=0.0001,
        volatility=0.002,
    )

    assert high_risk > low_risk
    assert 0.0 <= high_risk <= 1.0
    assert 0.0 <= low_risk <= 1.0


def test_evaluate_health(calculator: AssetHealthCalculator) -> None:
    """Test full health evaluation parameters and score boundaries."""
    prices = [100.0, 100.5, 99.8, 100.2, 100.1]
    volumes = [500.0, 600.0, 450.0, 700.0, 800.0]
    spreads = [0.0005, 0.0006, 0.0005, 0.0004, 0.0005]

    report = calculator.evaluate_health(
        prices=prices,
        volumes=volumes,
        spreads=spreads,
        funding_rates=[0.0001, 0.0002, 0.0001],
        open_interests=[1000.0, 1100.0, 1200.0],
    )

    assert "liquidity" in report
    assert "spread" in report
    assert "volume" in report
    assert "volatility" in report
    assert "funding" in report
    assert "open_interest" in report
    assert "manipulation_risk" in report
    assert "health_score" in report

    assert 0.0 <= report["health_score"] <= 1.0
    assert 0.0 <= report["manipulation_risk"] <= 1.0
