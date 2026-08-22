"""Zone proximity scoring logic for the Confluence Engine."""

from __future__ import annotations

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternDirection
from confluence.core.models import SupportingFactor, ConflictingFactor


def evaluate_zones(
    market_state: MarketState,
    pattern_direction: PatternDirection | None = None,
) -> tuple[float, list[SupportingFactor], list[ConflictingFactor]]:
    """Evaluate supply/demand zone proximity [0.0, 100.0]."""
    supporting = []
    conflicting = []

    zones = market_state.zones
    if not zones:
        return 70.0, [], []

    # Get latest price/swing price to check proximity
    latest_swing = market_state.swings[-1] if market_state.swings else None
    if not latest_swing:
        return 70.0, [], []

    score = 75.0
    for zone in zones:
        zone_type = getattr(zone, "zone_type", None)
        if not zone_type:
            continue
        
        type_str = str(zone_type).upper()
        is_demand = "DEMAND" in type_str
        is_supply = "SUPPLY" in type_str

        # Check if latest price is close/within zone boundaries
        low_bound = getattr(zone, "lower_bound", 0.0) or getattr(zone, "low_boundary", 0.0) or getattr(zone, "low", 0.0)
        high_bound = getattr(zone, "upper_bound", 0.0) or getattr(zone, "high_boundary", 0.0) or getattr(zone, "high", 0.0)

        in_zone = low_bound <= latest_swing.price <= high_bound

        if in_zone:
            if pattern_direction == PatternDirection.BULLISH and is_demand:
                supporting.append(
                    SupportingFactor(
                        name="Demand Zone Mitigation",
                        category="ZONES",
                        value=95.0,
                        description="Bullish pattern mitigated within structural demand zone.",
                    )
                )
                score = 95.0
            elif pattern_direction == PatternDirection.BEARISH and is_supply:
                supporting.append(
                    SupportingFactor(
                        name="Supply Zone Mitigation",
                        category="ZONES",
                        value=95.0,
                        description="Bearish pattern mitigated within structural supply zone.",
                    )
                )
                score = 95.0

    return score, supporting, conflicting
