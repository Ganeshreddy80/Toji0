"""Unit tests for the Regime Engine."""

from __future__ import annotations

import pytest
from intelligence.regime.engine import RegimeEngine


@pytest.fixture
def engine() -> RegimeEngine:
    """Provide a fresh RegimeEngine instance."""
    return RegimeEngine(
        compression_threshold=0.002,
        expansion_threshold=0.02,
        trend_threshold=0.15,
    )


def test_compression_detection(engine: RegimeEngine) -> None:
    """Test detection of volatility compression."""
    # Prices vary extremely little
    prices = [100.0, 100.01, 100.0, 99.99, 100.0]
    volumes = [10.0, 10.0, 10.0, 10.0, 10.0]

    assert engine.detect_regime(prices, volumes) == "Compression"


def test_markup_detection(engine: RegimeEngine) -> None:
    """Test detection of markup (bullish trend)."""
    # Strong upward trend
    prices = [100.0, 102.0, 104.0, 106.0, 109.0, 112.0]
    volumes = [10.0, 12.0, 15.0, 18.0, 20.0, 22.0]

    assert engine.detect_regime(prices, volumes) == "Markup"


def test_markdown_detection(engine: RegimeEngine) -> None:
    """Test detection of markdown (bearish trend)."""
    # Strong downward trend
    prices = [100.0, 97.0, 94.0, 91.0, 88.0, 85.0]
    volumes = [10.0, 12.0, 15.0, 18.0, 20.0, 22.0]

    assert engine.detect_regime(prices, volumes) == "Markdown"


def test_expansion_detection(engine: RegimeEngine) -> None:
    """Test detection of expansion (extreme volatility, expanding volume)."""
    # Large variance in price and volume burst
    prices = [100.0, 115.0, 90.0, 130.0, 75.0, 140.0]
    volumes = [10.0, 12.0, 11.0, 15.0, 20.0, 45.0]

    assert engine.detect_regime(prices, volumes) == "Expansion"


def test_accumulation_detection(engine: RegimeEngine) -> None:
    """Test detection of accumulation (consolidating at bottom with steady volume)."""
    # Ranging (trend <= 0.15), at bottom range (position < 0.35), volume rising (volume_trend >= 1.0)
    prices = [100.2, 100.5, 100.0, 99.5, 99.6, 99.5, 99.7]
    volumes = [10.0, 10.0, 10.0, 10.0, 12.0, 15.0, 18.0]

    assert engine.detect_regime(prices, volumes) == "Accumulation"


def test_distribution_detection(engine: RegimeEngine) -> None:
    """Test detection of distribution (consolidating at top with volume support)."""
    # Ranging (trend <= 0.15), at top range (position > 0.65)
    prices = [99.8, 99.5, 100.0, 100.5, 100.4, 100.5, 100.3]
    volumes = [10.0, 10.0, 10.0, 10.0, 15.0, 20.0, 25.0]

    assert engine.detect_regime(prices, volumes) == "Distribution"


def test_recovery_detection(engine: RegimeEngine) -> None:
    """Test detection of recovery phase (slight positive shift at range bottom)."""
    # Ranging, position < 0.35, but falling volume (volume_trend < 1.0)
    prices = [100.2, 100.5, 100.0, 99.5, 99.6, 99.5, 99.7]
    volumes = [20.0, 20.0, 20.0, 15.0, 12.0, 10.0, 8.0]

    assert engine.detect_regime(prices, volumes) == "Recovery"
