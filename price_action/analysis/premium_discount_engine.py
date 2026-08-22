"""Premium / Discount dealing range engine."""

from __future__ import annotations

import logging
from typing import List

from price_action.core.enums import SwingType, ZoneType
from price_action.core.interfaces import IPremiumDiscountEngine
from price_action.core.models import (
    PriceActionConfig,
    PriceActionSwing,
    PremiumDiscountState,
)

logger = logging.getLogger(__name__)


class PremiumDiscountEngine(IPremiumDiscountEngine):
    """Calculates dealing range equilibrium, premium, and discount zones."""

    def calculate_zones(
        self, current_price: float, swings: List[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> PremiumDiscountState | None:
        """Determine equilibrium, discount, premium, and current zone classification."""
        if not swings or current_price <= 0.0:
            return None

        swing_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
        swing_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]

        if not swing_highs or not swing_lows:
            return None

        high_p = max(s.price for s in swing_highs)
        low_p = min(s.price for s in swing_lows)

        if high_p <= low_p:
            return None

        rng = high_p - low_p
        eq = low_p + (rng * 0.50)
        deep_disc = low_p + (rng * 0.25)
        deep_prem = low_p + (rng * 0.75)

        zone = ZoneType.EQUILIBRIUM
        if current_price < deep_disc:
            zone = ZoneType.DEEP_DISCOUNT
        elif current_price < eq:
            zone = ZoneType.DISCOUNT
        elif current_price > deep_prem:
            zone = ZoneType.DEEP_PREMIUM
        elif current_price > eq:
            zone = ZoneType.PREMIUM

        return PremiumDiscountState(
            swing_high=round(high_p, 4),
            swing_low=round(low_p, 4),
            equilibrium=round(eq, 4),
            discount_upper=round(eq, 4),
            premium_lower=round(eq, 4),
            deep_discount_upper=round(deep_disc, 4),
            deep_premium_lower=round(deep_prem, 4),
            current_zone=zone,
        )
