"""Market Context Engine for combining low-level features into a unified context snapshot."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import MarketRegime, TrendDirection
from market_intelligence.core.events import MarketContextUpdated
from market_intelligence.core.models import (
    LiquidityState,
    MarketContext,
    SessionState,
    SRLevel,
    TimeframeAlignment,
    VolumeState,
    Zone,
)
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class MarketContextEngine:
    """Combines volume, structure, trend, regime, alignment, liquidity, and S&R states into MarketContext."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus

    def process_context(
        self,
        symbol: str,
        timeframe: str,
        dominant_trend: TrendDirection,
        session_state: SessionState | None,
        regime: MarketRegime,
        alignment: TimeframeAlignment,
        liquidity: LiquidityState | None,
        active_zones: list[Zone],
        volume_state: VolumeState | None,
        correlation: dict[str, float],
        sr_levels: list[SRLevel],
        timestamp: Any,
    ) -> MarketContext:
        """Synthesize all inputs into a single immutable MarketContext and publish it."""
        
        # Calculate confidence inputs (quantitative factors for future confidence calculations)
        confidence_inputs = {
            "alignment_score": alignment.alignment_score,
            "conflict_score": alignment.conflict_score,
            "higher_timeframe_confirmed": 1.0 if alignment.higher_timeframe_confirmation else 0.0,
            "normalized_volume": volume_state.normalized_volume if volume_state else 1.0,
            "zones_count": float(len([z for z in active_zones if not z.is_invalidated])),
            "sr_levels_count": float(len(sr_levels)),
        }

        context = MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            dominant_trend=dominant_trend,
            session=session_state,
            regime=regime,
            alignment=alignment,
            liquidity=liquidity,
            active_zones=active_zones,
            volume_context=volume_state,
            correlation=correlation,
            support_resistance=sr_levels,
            confidence_inputs=confidence_inputs,
            timestamp=timestamp,
        )

        self._publish_event(context)
        return context

    def _publish_event(self, context: MarketContext) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": context.symbol,
            "timeframe": context.timeframe,
            "dominant_trend": context.dominant_trend.value,
            "session": context.session.model_dump() if context.session else None,
            "regime": context.regime.value,
            "alignment": context.alignment.model_dump(),
            "liquidity": context.liquidity.model_dump() if context.liquidity else None,
            "active_zones": [z.model_dump() for z in context.active_zones],
            "volume_context": context.volume_context.model_dump() if context.volume_context else None,
            "correlation": context.correlation,
            "support_resistance": [lvl.model_dump() for lvl in context.support_resistance],
            "confidence_inputs": context.confidence_inputs,
            "timestamp": context.timestamp.isoformat(),
        }

        event = MarketContextUpdated(
            source="market_intelligence.context_engine",
            payload=payload,
        )
        self._event_bus.publish(event)
