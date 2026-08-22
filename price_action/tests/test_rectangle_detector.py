"""Unit tests for the RectangleDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.rectangle_detector import RectangleDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_rectangle_candidate_and_breakout():
    """Verify Rectangle candidate and breakout detection."""
    detector = RectangleDetector()

    # Preceding up-move: 50 -> 100
    # Consolidation range: highs around 100, lows around 80
    swings_cand = [
        make_swing(10, 50.0, SwingType.LOW),
        make_swing(15, 100.0, SwingType.HIGH),
        make_swing(20, 80.0, SwingType.LOW),
        make_swing(25, 100.0, SwingType.HIGH),
        make_swing(30, 80.0, SwingType.LOW),
    ]

    market_state = MarketState(
        symbol="BTCUSDT",
        timeframe="1h",
        swings=swings_cand,
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
    assert candidates[0].pattern_type == PatternType.RECTANGLE
    assert candidates[0].direction == PatternDirection.BULLISH
    assert len(matches) == 0

    # Trigger breakout above 100
    swings_break = swings_cand + [
        make_swing(35, 105.0, SwingType.HIGH)
    ]
    market_state = market_state.model_copy(update={"swings": swings_break})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.RECTANGLE
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED
