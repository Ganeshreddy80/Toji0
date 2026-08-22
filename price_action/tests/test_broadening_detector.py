"""Unit tests for the BroadeningDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.broadening_detector import BroadeningDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_broadening_candidate_and_breakout():
    """Verify Broadening Formation candidate and breakout detection."""
    detector = BroadeningDetector()

    # Broadening swings:
    # Swing 1: High at 10, price 100.0
    # Swing 2: Low at 20, price 90.0
    # Swing 3: High at 30, price 110.0
    # Swing 4: Low at 40, price 80.0
    swings = [
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(20, 90.0, SwingType.LOW),
        make_swing(30, 110.0, SwingType.HIGH),
        make_swing(40, 80.0, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.BROADENING
    assert len(matches) == 0

    # Bullish breakout above high line (at index 50, high line is at 120.0)
    swings_bull = swings + [make_swing(50, 125.0, SwingType.HIGH)]
    market_state_bull = market_state.model_copy(update={"swings": swings_bull})

    candidates, matches = detector.detect(market_state_bull)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.BROADENING
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED

    # Bearish breakout below low line (at index 50, low line is at 75.0)
    swings_bear = swings + [make_swing(50, 70.0, SwingType.LOW)]
    market_state_bear = market_state.model_copy(update={"swings": swings_bear})

    candidates, matches = detector.detect(market_state_bear)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.BROADENING
    assert matches[0].direction == PatternDirection.BEARISH
    assert matches[0].status == PatternStatus.CONFIRMED
