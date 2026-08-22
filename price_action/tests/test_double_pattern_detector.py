"""Unit tests for the DoublePatternDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.double_pattern_detector import DoublePatternDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_double_top_candidate_and_breakout():
    """Verify Double Top candidate and breakout detection."""
    detector = DoublePatternDetector()

    # Double Top: Peak 1 at 100, Neckline at 80, Peak 2 at 100, Breakout below 80
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
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
    assert candidates[0].pattern_type == PatternType.DOUBLE_TOP
    assert len(matches) == 0

    # Trigger breakout
    swings.append(make_swing(25, 75.0, SwingType.LOW))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.DOUBLE_TOP
    assert matches[0].direction == PatternDirection.BEARISH
    assert matches[0].status == PatternStatus.CONFIRMED


def test_double_bottom_candidate_and_breakout():
    """Verify Double Bottom candidate and breakout detection."""
    detector = DoublePatternDetector()

    # Double Bottom: Trough 1 at 50, Neckline at 70, Trough 2 at 50, Breakout above 70
    swings = [
        make_swing(10, 50.0, SwingType.LOW),
        make_swing(15, 70.0, SwingType.HIGH),
        make_swing(20, 50.0, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.DOUBLE_BOTTOM
    assert len(matches) == 0

    # Trigger breakout
    swings.append(make_swing(25, 75.0, SwingType.HIGH))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.DOUBLE_BOTTOM
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED
