"""Unit tests for the HeadShouldersDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.head_shoulders_detector import HeadShouldersDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_head_shoulders_candidate_and_breakout():
    """Verify Head & Shoulders candidate and breakout detection."""
    detector = HeadShouldersDetector()

    # H&S: Left Shoulder = 90, Neckline 1 = 80, Head = 100, Neckline 2 = 80, Right Shoulder = 90
    swings = [
        make_swing(10, 90.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
        make_swing(25, 80.0, SwingType.LOW),
        make_swing(30, 90.0, SwingType.HIGH),
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
    assert candidates[0].pattern_type == PatternType.HEAD_AND_SHOULDERS
    assert len(matches) == 0

    # Breakout below neckline (which is at 80)
    swings.append(make_swing(35, 75.0, SwingType.LOW))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.HEAD_AND_SHOULDERS
    assert matches[0].direction == PatternDirection.BEARISH
    assert matches[0].status == PatternStatus.CONFIRMED


def test_inverse_head_shoulders_candidate_and_breakout():
    """Verify Inverse Head & Shoulders candidate and breakout detection."""
    detector = HeadShouldersDetector()

    # Inverse H&S: Left Shoulder = 60, Neckline 1 = 70, Head = 50, Neckline 2 = 70, Right Shoulder = 60
    swings = [
        make_swing(10, 60.0, SwingType.LOW),
        make_swing(15, 70.0, SwingType.HIGH),
        make_swing(20, 50.0, SwingType.LOW),
        make_swing(25, 70.0, SwingType.HIGH),
        make_swing(30, 60.0, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.INVERSE_HEAD_AND_SHOULDERS
    assert len(matches) == 0

    # Breakout above neckline (70)
    swings.append(make_swing(35, 75.0, SwingType.HIGH))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.INVERSE_HEAD_AND_SHOULDERS
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED
