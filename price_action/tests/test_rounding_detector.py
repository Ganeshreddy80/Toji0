"""Unit tests for the RoundingDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.rounding_detector import RoundingDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_rounded_bottom_candidate_and_breakout():
    """Verify Rounded Bottom candidate and breakout detection."""
    detector = RoundingDetector()

    # Rounded Bottom: U-shape
    # y = (x - 20)^2 + 50
    # indices: 10, 15, 20, 25, 30
    swings = [
        make_swing(10, 150.0, SwingType.HIGH),
        make_swing(15, 75.0, SwingType.LOW),
        make_swing(20, 50.0, SwingType.HIGH),
        make_swing(25, 75.0, SwingType.LOW),
        make_swing(30, 150.0, SwingType.HIGH),
    ]

    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )

    candidates, matches = detector.detect(market_state)
    assert len(candidates) == 1
    assert candidates[0].pattern_type == PatternType.ROUNDED_BOTTOM
    assert len(matches) == 0

    # Bullish breakout above lip level (150.0)
    swings.append(make_swing(35, 160.0, SwingType.HIGH))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.ROUNDED_BOTTOM
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED


def test_rounded_top_candidate_and_breakout():
    """Verify Rounded Top candidate and breakout detection."""
    detector = RoundingDetector()

    # Rounded Top: inverted U-shape
    # y = -(x - 20)^2 + 150
    # indices: 10, 15, 20, 25, 30
    swings = [
        make_swing(10, 50.0, SwingType.LOW),
        make_swing(15, 125.0, SwingType.HIGH),
        make_swing(20, 150.0, SwingType.LOW),
        make_swing(25, 125.0, SwingType.HIGH),
        make_swing(30, 50.0, SwingType.LOW),
    ]

    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings,
        trend=None,
        liquidity=None,
        zones=[],
        session=None,
        volume=None,
        context=None,
        confidence=None,
        story=None,
        structure_history=[],
        bos_history=[],
        choch_history=[],
        sr_levels=[],
        market_phase_state="Unknown",
        market_context=None,
        updated_at=datetime.now(timezone.utc),
    )

    candidates, matches = detector.detect(market_state)
    assert len(candidates) == 1
    assert candidates[0].pattern_type == PatternType.ROUNDED_TOP
    assert len(matches) == 0

    # Bearish breakout below lip level (50.0)
    swings.append(make_swing(35, 40.0, SwingType.LOW))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.ROUNDED_TOP
    assert matches[0].direction == PatternDirection.BEARISH
    assert matches[0].status == PatternStatus.CONFIRMED
