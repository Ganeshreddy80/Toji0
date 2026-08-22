"""Unit tests for the ChannelDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.channel_detector import ChannelDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_ascending_channel_breakout():
    """Verify detection of an Ascending Channel with a bullish breakout."""
    detector = ChannelDetector()
    
    # Both slopes around 0.5. Breakout above upper line.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 85.0, SwingType.LOW),
        make_swing(20, 105.0, SwingType.HIGH),
        make_swing(25, 90.0, SwingType.LOW),
        make_swing(30, 110.0, SwingType.HIGH),
        make_swing(35, 115.0, SwingType.HIGH),  # Breakout above upper line (112.5)
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
    assert match.pattern_type == PatternType.ASC_CHANNEL
    assert match.direction == PatternDirection.BULLISH
    assert match.status == PatternStatus.CONFIRMED


def test_descending_channel_breakout():
    """Verify detection of a Descending Channel with a bearish breakout."""
    detector = ChannelDetector()
    
    # Both slopes around -0.5. Breakout below lower line.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 95.0, SwingType.HIGH),
        make_swing(25, 75.0, SwingType.LOW),
        make_swing(30, 90.0, SwingType.HIGH),
        make_swing(35, 65.0, SwingType.LOW),  # Breakout below lower line (70.0)
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
    assert match.pattern_type == PatternType.DESC_CHANNEL
    assert match.direction == PatternDirection.BEARISH
    assert match.status == PatternStatus.CONFIRMED


def test_horizontal_channel_breakout():
    """Verify detection of a Horizontal Channel with a bullish breakout."""
    detector = ChannelDetector()
    
    # Slopes around 0. Breakout above upper line.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
        make_swing(25, 80.0, SwingType.LOW),
        make_swing(30, 100.0, SwingType.HIGH),
        make_swing(35, 105.0, SwingType.HIGH),  # Breakout above upper line (100.0)
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
    assert match.pattern_type == PatternType.CHANNEL
    assert match.direction == PatternDirection.BULLISH
    assert match.status == PatternStatus.CONFIRMED
