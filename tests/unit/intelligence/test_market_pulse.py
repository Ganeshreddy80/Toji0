"""Unit tests for the Market Pulse Generator."""

from __future__ import annotations

import pytest
from intelligence.market_pulse.pulse import MarketPulseGenerator


@pytest.fixture
def generator() -> MarketPulseGenerator:
    """Provide a fresh MarketPulseGenerator."""
    return MarketPulseGenerator()


def test_calculate_trend(generator: MarketPulseGenerator) -> None:
    """Test trend indicators with positive, negative, and flat price series."""
    bullish_prices = [100.0, 101.0, 102.0, 103.0, 105.0]
    bearish_prices = [100.0, 98.0, 97.0, 96.0, 94.0]
    flat_prices = [100.0, 100.0, 100.1, 99.9, 100.0]

    assert generator.calculate_trend(bullish_prices) > 0.0
    assert generator.calculate_trend(bearish_prices) < 0.0
    assert abs(generator.calculate_trend(flat_prices)) < 0.05
    assert generator.calculate_trend([100.0]) == 0.0


def test_calculate_momentum(generator: MarketPulseGenerator) -> None:
    """Test momentum indicators with rising and falling trends."""
    accelerating_prices = [100.0, 100.2, 100.5, 101.0, 103.0, 106.0]
    decelerating_prices = [100.0, 105.0, 108.0, 109.0, 109.2, 109.3]

    assert generator.calculate_momentum(accelerating_prices) > 0.0
    assert generator.calculate_momentum(decelerating_prices) < 0.5


def test_calculate_volatility(generator: MarketPulseGenerator) -> None:
    """Test volatility calculations with high and low variance series."""
    stable_prices = [100.0, 100.1, 100.0, 100.2, 100.1]
    volatile_prices = [100.0, 110.0, 90.0, 120.0, 80.0]

    stable_vol = generator.calculate_volatility(stable_prices)
    volatile_vol = generator.calculate_volatility(volatile_prices)

    assert volatile_vol > stable_vol
    assert generator.calculate_volatility([100.0, 100.0]) == 0.0


def test_generate_pulse(generator: MarketPulseGenerator) -> None:
    """Test full MarketPulse object synthesis, asserting limits and constraints."""
    prices = [100.0, 101.0, 102.0, 103.0, 105.0]
    volumes = [10.0, 12.0, 11.0, 15.0, 20.0]
    bids = [(104.9, 5.0), (104.8, 10.0)]
    asks = [(105.1, 4.0), (105.2, 8.0)]

    pulse = generator.generate_pulse(
        prices=prices,
        volumes=volumes,
        bids=bids,
        asks=asks,
        fear_index=45.0,
        confidence=0.9,
    )

    assert pulse.trend > 0.0
    assert pulse.momentum > 0.0
    assert pulse.liquidity > 0.0
    assert pulse.participation > 0.0
    assert 0.0 <= pulse.risk <= 1.0
    assert 0.0 <= pulse.overall_score <= 1.0
