"""Unit tests for the HarmonicDetector module."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import MarketState, SwingPoint
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.analysis.harmonic_detector import HarmonicDetector, HarmonicLegs, HarmonicValidator


def make_swing(index: int, price: float, point_type: SwingType) -> SwingPoint:
    return SwingPoint(
        symbol="BTCUSDT",
        timeframe="1h",
        point_type=point_type,
        price=price,
        timestamp=datetime.fromtimestamp(index * 3600, tz=timezone.utc),
        index=index,
    )


def test_harmonic_leg_extraction_and_validator():
    """Verify leg extraction and harmonic ratio validation functionality."""
    x = make_swing(10, 100.0, SwingType.LOW)
    a = make_swing(20, 200.0, SwingType.HIGH)
    b = make_swing(30, 138.2, SwingType.LOW)
    c = make_swing(40, 176.4, SwingType.HIGH)
    d = make_swing(50, 114.6, SwingType.LOW)

    legs = HarmonicLegs(x, a, b, c, d)
    assert abs(legs.ab_xa_ratio - 0.618) < 0.01
    assert abs(legs.bc_ab_ratio - 0.618) < 0.01
    assert abs(legs.cd_bc_ratio - 1.618) < 0.01

    # Validate against standard targets
    ab_xa_targets = [0.618]
    bc_ab_targets = [0.618]
    cd_bc_targets = [1.618]
    assert HarmonicValidator.validate_structure(legs, ab_xa_targets, bc_ab_targets, cd_bc_targets, tolerance=0.02)


def test_harmonic_candidate_and_breakout():
    """Verify Harmonic pattern candidate and breakout detection."""
    detector = HarmonicDetector()

    # Harmonic structure (bullish): Low, High, Low, High, Low
    swings = [
        make_swing(10, 100.0, SwingType.LOW),
        make_swing(20, 200.0, SwingType.HIGH),
        make_swing(30, 138.2, SwingType.LOW),
        make_swing(40, 176.4, SwingType.HIGH),
        make_swing(50, 114.6, SwingType.LOW),
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
    assert candidates[0].pattern_type == PatternType.HARMONIC
    assert len(matches) == 0

    # Bullish breakout above D's price (114.6)
    swings.append(make_swing(60, 120.0, SwingType.HIGH))
    market_state = market_state.model_copy(update={"swings": swings})

    candidates, matches = detector.detect(market_state)
    assert len(matches) == 1
    assert matches[0].pattern_type == PatternType.HARMONIC
    assert matches[0].direction == PatternDirection.BULLISH
    assert matches[0].status == PatternStatus.CONFIRMED
