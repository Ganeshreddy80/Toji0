"""Story Generator for creating descriptive market narrative summaries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from market_intelligence.core.events import MarketStoryGenerated
from market_intelligence.core.models import (
    ConfidenceState,
    MarketContext,
    MarketState,
    StoryState,
)
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class StoryGenerator:
    """Generates structured narrative of market context without trading recommendations."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus

    def generate(
        self,
        market_state: MarketState,
        market_context: MarketContext,
        confidence_state: ConfidenceState,
        timestamp: datetime,
    ) -> StoryState:
        """Generate 9-section market story, compile supporting events, and publish."""
        sections = {}
        supporting_events = []

        # 1. Current Trend
        if market_state.trend:
            direction = market_state.trend.direction.value
            strength = market_state.trend.strength
            duration_str = f"starting at {market_state.trend.start_time.isoformat()}"
            sections["Current Trend"] = (
                f"Market trend is {direction} with a strength of {strength:.2f}, {duration_str}."
            )
            supporting_events.append(f"Trend direction: {direction} (strength: {strength:.2f})")
        else:
            sections["Current Trend"] = "No active trend direction detected."

        # 2. Current Structure
        hh_hl_lh_ll = [p.classification for p in market_state.structure_history[-5:]]
        struct_summary = ", ".join(hh_hl_lh_ll) if hh_hl_lh_ll else "None"
        bos_count = len(market_state.bos_history)
        choch_count = len(market_state.choch_history)
        sections["Current Structure"] = (
            f"Recent swing structures: [{struct_summary}]. "
            f"Break of Structure (BOS) count: {bos_count}. Change of Character (CHoCH) count: {choch_count}."
        )
        if market_state.bos_history:
            supporting_events.append(f"Total BOS breakout events: {bos_count}")
        if market_state.choch_history:
            supporting_events.append(f"Total CHoCH reversal events: {choch_count}")

        # 3. Liquidity
        if market_state.liquidity:
            buys = len(market_state.liquidity.buy_side_pools)
            sells = len(market_state.liquidity.sell_side_pools)
            swept = len(market_state.liquidity.swept_levels)
            sections["Liquidity"] = (
                f"Active liquidity pools: {buys} buy-side pools, {sells} sell-side pools. "
                f"Recently swept levels count: {swept}."
            )
            if swept > 0:
                supporting_events.append(f"Active liquidity swept levels count: {swept}")
        else:
            sections["Liquidity"] = "No liquidity pools tracked."

        # 4. Important Zones
        active_zones = [z for z in market_state.zones if not z.is_invalidated]
        supply_count = len([z for z in active_zones if z.zone_type.value == "SUPPLY"])
        demand_count = len([z for z in active_zones if z.zone_type.value == "DEMAND"])
        mitigations = sum(z.mitigations_count for z in active_zones)
        sections["Important Zones"] = (
            f"Active zones: {supply_count} supply zones and {demand_count} demand zones. "
            f"Cumulative mitigation touches: {mitigations}."
        )
        if active_zones:
            supporting_events.append(f"Active supply/demand zones: {len(active_zones)}")

        # 5. Volume Context
        if market_state.volume:
            norm_vol = market_state.volume.normalized_volume
            expansion = market_state.volume.expansion_state.value
            sections["Volume Context"] = (
                f"Normalized volume is {norm_vol:.2f}. "
                f"Volume expansion state: {expansion}."
            )
            if expansion != "NORMAL":
                supporting_events.append(f"Volume state is in {expansion} expansion")
        else:
            sections["Volume Context"] = "No volume context state available."

        # 6. Market Regime
        regime = market_context.regime.value
        sections["Market Regime"] = f"Current classified market regime: {regime}."
        supporting_events.append(f"Regime classification: {regime}")

        # 7. Higher Timeframe Context
        align = market_context.alignment
        sections["Higher Timeframe Context"] = (
            f"Dominant trend across timeframes: {align.dominant_trend.value}. "
            f"Alignment score: {align.alignment_score:.2f}, Conflict score: {align.conflict_score:.2f}. "
            f"HTF confirmation status: {'CONFIRMED' if align.higher_timeframe_confirmation else 'UNCONFIRMED'}."
        )
        if align.higher_timeframe_confirmation:
            supporting_events.append("Higher timeframe trend confirmation received")

        # 8. Correlation Summary
        top_corr = sorted(market_context.correlation.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
        corr_items = [f"{symbol}={val:.2f}" for symbol, val in top_corr]
        sections["Correlation Summary"] = (
            f"Tracked asset correlations: {', '.join(corr_items) if corr_items else 'None'}."
        )

        # 9. Overall Confidence
        sorted_contribs = sorted(confidence_state.contribution_breakdown.items(), key=lambda x: x[1], reverse=True)[:3]
        contrib_items = [f"{factor}={val:.2f}" for factor, val in sorted_contribs]
        sections["Overall Confidence"] = (
            f"Overall system confidence score: {confidence_state.score:.2f}. "
            f"Top contributing factors: {', '.join(contrib_items)}."
        )
        supporting_events.append(f"Confidence score updated to {confidence_state.score:.2f}")

        # Concatenate into single narrative string
        narrative = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items())

        state = StoryState(
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            narrative=narrative,
            sections=sections,
            supporting_events=supporting_events,
            generated_at=timestamp,
        )

        self._publish_event(state)
        return state

    def _publish_event(self, state: StoryState) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": state.symbol,
            "timeframe": state.timeframe,
            "sections": state.sections,
            "supporting_events": state.supporting_events,
            "generated_at": state.generated_at.isoformat(),
        }

        event = MarketStoryGenerated(
            source="market_intelligence.story_generator",
            payload=payload,
        )
        self._event_bus.publish(event)
