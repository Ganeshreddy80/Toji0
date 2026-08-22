"""Unit tests for PremiumDiscountEngine."""

from __future__ import annotations

from datetime import datetime, timezone
from price_action.analysis.premium_discount_engine import PremiumDiscountEngine
from price_action.core.enums import SwingType, ZoneType
from price_action.core.models import PriceActionSwing


def test_premium_discount_zones():
    engine = PremiumDiscountEngine()
    now = datetime.now(timezone.utc)

    swings = [
        PriceActionSwing(swing_type=SwingType.SWING_HIGH, price=200.0, timestamp=now, index=1),
        PriceActionSwing(swing_type=SwingType.SWING_LOW, price=100.0, timestamp=now, index=2),
    ]

    # Equilibrium is 150.0. Deep Discount < 125.0, Deep Premium > 175.0.
    state_disc = engine.calculate_zones(110.0, swings)
    assert state_disc is not None
    assert state_disc.current_zone == ZoneType.DEEP_DISCOUNT

    state_prem = engine.calculate_zones(180.0, swings)
    assert state_prem is not None
    assert state_prem.current_zone == ZoneType.DEEP_PREMIUM


def test_premium_discount_empty():
    engine = PremiumDiscountEngine()
    assert engine.calculate_zones(100.0, []) is None
