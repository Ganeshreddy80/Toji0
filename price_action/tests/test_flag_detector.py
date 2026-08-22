"""Unit tests for the FlagDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.flag_detector import FlagDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_bull_flag_breakout():
    """Verify detection of a Bull Flag with a bullish breakout."""
    detector = FlagDetector()
    
    # Pole: 80 -> 100. Consolidations slope downwards. Breakout on last swing.
    swings = [
        make_swing(5, 80.0, SwingType.LOW),
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 85.0, SwingType.LOW),
        make_swing(20, 98.0, SwingType.HIGH),
        make_swing(25, 83.0, SwingType.LOW),
        make_swing(35, 96.0, SwingType.HIGH),  # Breakout above upper line
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
    assert match.pattern_type == PatternType.BULL_FLAG
    assert match.direction == PatternDirection.BULLISH
    assert match.status == PatternStatus.CONFIRMED


def test_bear_flag_breakout():
    """Verify detection of a Bear Flag with a bearish breakout."""
    detector = FlagDetector()
    
    # Pole: 100 -> 80. Consolidations slope upwards. Breakout on last swing.
    swings = [
        make_swing(5, 100.0, SwingType.HIGH),
        make_swing(10, 80.0, SwingType.LOW),
        make_swing(15, 90.0, SwingType.HIGH),
        make_swing(20, 82.0, SwingType.LOW),
        make_swing(25, 92.0, SwingType.HIGH),
        make_swing(35, 80.0, SwingType.LOW),  # Breakout below lower line
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
    assert match.pattern_type == PatternType.BEAR_FLAG
    assert match.direction == PatternDirection.BEARISH
    assert match.status == PatternStatus.CONFIRMED
