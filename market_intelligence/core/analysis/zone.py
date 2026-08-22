"""Supply and Demand Zone Engine for institutional block tracking."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import ZoneType
from market_intelligence.core.events import (
    DemandZoneCreated,
    SupplyZoneCreated,
    ZoneInvalidated,
    ZoneMitigated,
)
from market_intelligence.core.models import Zone
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class ZoneEngine:
    """Manages Supply and Demand zones lifecycle (creation, mitigation, invalidation)."""

    def __init__(self, event_bus: IEventBus | None = None, displacement_bars: int = 2) -> None:
        self._event_bus = event_bus
        self._displacement_bars = displacement_bars
        # Mapping: (symbol, timeframe) -> list of Zone objects
        self._zones: dict[tuple[str, str], list[Zone]] = {}
        # Keep track of created base candle indices to avoid duplicates
        self._created_indices: dict[tuple[str, str], set[int]] = {}

    def get_zones(self, symbol: str, timeframe: str) -> list[Zone]:
        """Get all zones (active and historical/invalidated)."""
        return self._zones.get((symbol, timeframe), [])

    def evaluate_zones(
        self,
        symbol: str,
        timeframe: str,
        history: list[Any],
        atr: float,
    ) -> list[Zone]:
        """Process the latest candle, evaluate active zone status, and check for new zones."""
        key = (symbol, timeframe)
        if key not in self._zones:
            self._zones[key] = []
            self._created_indices[key] = set()

        if len(history) < self._displacement_bars + 1:
            return []

        current_candle = history[-1]
        close_price = current_candle.close
        high_price = current_candle.high
        low_price = current_candle.low

        updated_zones: list[Zone] = []
        for zone in self._zones[key]:
            if zone.is_invalidated:
                updated_zones.append(zone)
                continue

            # 1. Check for Invalidation (body closes past the zone boundary)
            if zone.zone_type == ZoneType.SUPPLY:
                if close_price > zone.upper_bound:
                    # Invalidated!
                    zone = zone.model_copy(update={"is_invalidated": True})
                    self._publish_invalidation(zone, current_candle.timestamp)
                else:
                    # Check for Mitigation (wick touches the zone)
                    if high_price > zone.lower_bound:
                        zone = zone.model_copy(update={"mitigations_count": zone.mitigations_count + 1})
                        self._publish_mitigation(zone, current_candle.timestamp)
            else: # DEMAND
                if close_price < zone.lower_bound:
                    # Invalidated!
                    zone = zone.model_copy(update={"is_invalidated": True})
                    self._publish_invalidation(zone, current_candle.timestamp)
                else:
                    # Check for Mitigation (wick touches the zone)
                    if low_price < zone.upper_bound:
                        zone = zone.model_copy(update={"mitigations_count": zone.mitigations_count + 1})
                        self._publish_mitigation(zone, current_candle.timestamp)

            updated_zones.append(zone)

        self._zones[key] = updated_zones

        # 2. Check for New Zone Creation
        # We look at index t = len(history) - 1. Base is t - D.
        t = len(history) - 1
        d = self._displacement_bars
        base_idx = t - d

        if base_idx >= 0 and base_idx not in self._created_indices[key]:
            base_candle = history[base_idx]
            
            # Check Bearish Displacement (Supply Zone)
            is_bearish_displacement = True
            for i in range(1, d + 1):
                c = history[base_idx + i]
                if c.close >= c.open:
                    is_bearish_displacement = False
                    break
            
            if is_bearish_displacement:
                cumulative_decline = sum(history[base_idx + i].open - history[base_idx + i].close for i in range(1, d + 1))
                if atr > 0.0 and cumulative_decline > 2.0 * atr:
                    # Create Supply Zone
                    upper = max(base_candle.high, history[base_idx + 1].high)
                    lower = base_candle.close
                    
                    new_zone = Zone(
                        symbol=symbol,
                        timeframe=timeframe,
                        zone_type=ZoneType.SUPPLY,
                        upper_bound=upper,
                        lower_bound=lower,
                        volume_at_creation=base_candle.volume,
                        mitigations_count=0,
                        is_invalidated=False,
                    )
                    self._zones[key].append(new_zone)
                    self._created_indices[key].add(base_idx)
                    self._publish_creation(new_zone, current_candle.timestamp)

            # Check Bullish Displacement (Demand Zone)
            is_bullish_displacement = True
            for i in range(1, d + 1):
                c = history[base_idx + i]
                if c.close <= c.open:
                    is_bullish_displacement = False
                    break
            
            if is_bullish_displacement:
                cumulative_rise = sum(history[base_idx + i].close - history[base_idx + i].open for i in range(1, d + 1))
                if atr > 0.0 and cumulative_rise > 2.0 * atr:
                    # Create Demand Zone
                    upper = base_candle.close
                    lower = min(base_candle.low, history[base_idx + 1].low)
                    
                    new_zone = Zone(
                        symbol=symbol,
                        timeframe=timeframe,
                        zone_type=ZoneType.DEMAND,
                        upper_bound=upper,
                        lower_bound=lower,
                        volume_at_creation=base_candle.volume,
                        mitigations_count=0,
                        is_invalidated=False,
                    )
                    self._zones[key].append(new_zone)
                    self._created_indices[key].add(base_idx)
                    self._publish_creation(new_zone, current_candle.timestamp)

        return self._zones[key]

    def _publish_creation(self, zone: Zone, timestamp: Any) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": zone.symbol,
            "timeframe": zone.timeframe,
            "upper_bound": zone.upper_bound,
            "lower_bound": zone.lower_bound,
            "volume_at_creation": zone.volume_at_creation,
            "timestamp": timestamp.isoformat(),
        }

        if zone.zone_type == ZoneType.SUPPLY:
            event = SupplyZoneCreated(source="market_intelligence.zone_engine", payload=payload)
        else:
            event = DemandZoneCreated(source="market_intelligence.zone_engine", payload=payload)

        self._event_bus.publish(event)

    def _publish_mitigation(self, zone: Zone, timestamp: Any) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": zone.symbol,
            "timeframe": zone.timeframe,
            "zone_type": zone.zone_type.value,
            "upper_bound": zone.upper_bound,
            "lower_bound": zone.lower_bound,
            "mitigations_count": zone.mitigations_count,
            "timestamp": timestamp.isoformat(),
        }

        event = ZoneMitigated(source="market_intelligence.zone_engine", payload=payload)
        self._event_bus.publish(event)

    def _publish_invalidation(self, zone: Zone, timestamp: Any) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": zone.symbol,
            "timeframe": zone.timeframe,
            "zone_type": zone.zone_type.value,
            "upper_bound": zone.upper_bound,
            "lower_bound": zone.lower_bound,
            "timestamp": timestamp.isoformat(),
        }

        event = ZoneInvalidated(source="market_intelligence.zone_engine", payload=payload)
        self._event_bus.publish(event)
