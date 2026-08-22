"""Unit tests for the WedgeDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.wedge_detector import WedgeDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_rising_wedge_breakout():
    """Verify detection of a Rising Wedge with a bearish breakout."""
    detector = WedgeDetector()
    
    # Both rising, lower line steeper. Breakout below lower line.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 85.0, SwingType.LOW),
        make_swing(20, 104.0, SwingType.HIGH),
        make_swing(25, 91.0, SwingType.LOW),
        make_swing(30, 108.0, SwingType.HIGH),
        make_swing(35, 94.0, SwingType.LOW),  # Breakout below lower line (97.0)
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
    assert len(matches) == 1
    
    match = matches[0]
    assert match.pattern_type == PatternType.RISING_WEDGE
    assert match.direction == PatternDirection.BEARISH
    assert match.status == PatternStatus.CONFIRMED


def test_falling_wedge_breakout():
    """Verify detection of a Falling Wedge with a bullish breakout."""
    detector = WedgeDetector()
    
    # Both falling, upper line steeper. Breakout above upper line.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 92.0, SwingType.HIGH),
        make_swing(25, 74.0, SwingType.LOW),
        make_swing(30, 84.0, SwingType.HIGH),
        make_swing(35, 84.0, SwingType.HIGH),  # Breakout above upper line (80.0)
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
    assert len(matches) == 1
    
    match = matches[0]
    assert match.pattern_type == PatternType.FALLING_WEDGE
    assert match.direction == PatternDirection.BULLISH
    assert match.status == PatternStatus.CONFIRMED
