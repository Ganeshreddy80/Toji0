"""Unit tests for the CupHandleDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.cup_handle_detector import CupHandleDetector


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_cup_handle_candidate_and_breakout():
    """Verify Cup & Handle candidate and breakout detection."""
    detector = CupHandleDetector()

    # Cup & Handle:
    # Swing 1: Low at 40 (preceding)
    # Swing 2: High at 100 (Left Lip)
    # Swing 3: Low at 50 (Cup Bottom)
    # Swing 4: High at 100 (Right Lip)
    # Swing 5: Low at 80 (Handle Low)
    swings = [
        make_swing(5, 40.0, SwingType.LOW),
        make_swing(10, 100.0, SwingType.HIGH),
        make_swing(20, 50.0, SwingType.LOW),
        make_swing(30, 100.0, SwingType.HIGH),
        make_swing(35, 80.0, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.CUP_AND_HANDLE
    assert len(matches) == 0

    # Trigger breakout (Right Lip price is 100.0, so breakout above 100.0)
    swings.append(make_swing(40, 105.0, SwingType.HIGH))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.CUP_AND_HANDLE
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED
