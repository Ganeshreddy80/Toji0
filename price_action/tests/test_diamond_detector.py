"""Unit tests for the DiamondDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.diamond_detector import DiamondDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_diamond_top_candidate_and_breakout():
    """Verify Diamond Top candidate and breakout detection."""
    detector = DiamondDetector()

    # Diamond Top: starts from below (uptrend)
    # Swing 1: Low at 5, price 50
    # Swing 2: High at 10, price 100
    # Swing 3: Low at 15, price 80
    # Swing 4: High at 20, price 110
    # Swing 5: Low at 25, price 70
    # Swing 6: High at 30, price 95
    # Swing 7: Low at 35, price 85
    swings = [
        make_swing(5, 50.0, SwingType.LOW),
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 110.0, SwingType.HIGH),
        make_swing(25, 70.0, SwingType.LOW),
        make_swing(30, 95.0, SwingType.HIGH),
        make_swing(35, 85.0, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.DIAMOND_TOP
    assert len(matches) == 0

    # Bearish breakout below lower-right trendline (line value at 40 is 92.5)
    swings.append(make_swing(40, 90.0, SwingType.LOW))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.DIAMOND_TOP
    assert matches[0].direction == PatternDirection.BEARISH
    assert matches[0].status == PatternStatus.CONFIRMED


def test_diamond_bottom_candidate_and_breakout():
    """Verify Diamond Bottom candidate and breakout detection."""
    detector = DiamondDetector()

    # Diamond Bottom: starts from above (downtrend)
    # Swing 1: High at 5, price 120
    # Swing 2: High at 10, price 100
    # Swing 3: Low at 15, price 80
    # Swing 4: High at 20, price 110
    # Swing 5: Low at 25, price 70
    # Swing 6: High at 30, price 95
    # Swing 7: Low at 35, price 85
    swings = [
        make_swing(5, 120.0, SwingType.HIGH),
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 110.0, SwingType.HIGH),
        make_swing(25, 70.0, SwingType.LOW),
        make_swing(30, 95.0, SwingType.HIGH),
        make_swing(35, 85.0, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.DIAMOND_BOTTOM
    assert len(matches) == 0

    # Bullish breakout above upper-right trendline (line value at 40 is 80)
    swings.append(make_swing(40, 85.0, SwingType.HIGH))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.DIAMOND_BOTTOM
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED
