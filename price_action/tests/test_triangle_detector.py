"""Unit tests for the TriangleDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.triangle_detector import TriangleDetector
from price_action.core.models import PatternPoint


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_symmetrical_triangle_candidate():
    """Verify detection of a Symmetrical Triangle candidate (no breakout)."""
    detector = TriangleDetector()
    
    # Converging slopes: upper falling, lower rising
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 95.0, SwingType.HIGH),
        make_swing(25, 83.0, SwingType.LOW),
        make_swing(30, 90.0, SwingType.HIGH),
        make_swing(35, 86.0, SwingType.LOW),  # Inside, no breakout
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
    assert len(matches) == 0
    
    cand = candidates[0]
    assert cand.pattern_type == PatternType.SYMMETRIC_TRIANGLE
    assert cand.direction == PatternDirection.NEUTRAL
    assert cand.score > 0.8


def test_ascending_triangle_bullish_breakout():
    """Verify detection of an Ascending Triangle with a bullish breakout."""
    detector = TriangleDetector()
    
    # Upper flat, lower rising. Breakout at last swing.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 100.0, SwingType.HIGH),
        make_swing(25, 85.0, SwingType.LOW),
        make_swing(30, 100.0, SwingType.HIGH),
        make_swing(35, 105.0, SwingType.HIGH),  # Bullish breakout!
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
    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_type == PatternType.ASC_TRIANGLE
    assert match.direction == PatternDirection.BULLISH
    assert match.status == PatternStatus.CONFIRMED


def test_descending_triangle_bearish_breakout():
    """Verify detection of a Descending Triangle with a bearish breakout."""
    detector = TriangleDetector()
    
    # Upper falling, lower flat. Breakout at last swing.
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(15, 80.0, SwingType.LOW),
        make_swing(20, 95.0, SwingType.HIGH),
        make_swing(25, 80.0, SwingType.LOW),
        make_swing(30, 90.0, SwingType.HIGH),
        make_swing(35, 75.0, SwingType.LOW),  # Bearish breakout!
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
    assert len(matches) == 1
    match = matches[0]
    assert match.pattern_type == PatternType.DESC_TRIANGLE
    assert match.direction == PatternDirection.BEARISH
    assert match.status == PatternStatus.CONFIRMED
