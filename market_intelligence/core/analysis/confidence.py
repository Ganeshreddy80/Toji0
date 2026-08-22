"""Confidence Engine for calculating objective confidence score based on market context."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from market_intelligence.core.enums import (
    MarketRegime,
    SessionName,
    TrendDirection,
    VolumeExpansionState,
)
from market_intelligence.core.events import ConfidenceScoreUpdated, MarketConfidenceUpdated
from market_intelligence.core.models import (
    ConfidenceState,
    MarketContext,
    MarketState,
    MarketConfidence,
)
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """Calculates objective confidence score from analytical outputs."""

    DEFAULT_WEIGHTS = {
        "trend_weight": 0.15,
        "structure_weight": 0.10,
        "bos_weight": 0.10,
        "choch_weight": 0.05,
        "liquidity_weight": 0.10,
        "zone_weight": 0.10,
        "sr_weight": 0.05,
        "volume_weight": 0.10,
        "session_weight": 0.05,
        "alignment_weight": 0.10,
        "regime_weight": 0.05,
        "correlation_weight": 0.05,
    }

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._pydantic_confidences: dict[tuple[str, str], MarketConfidence] = {}

        # Verify and normalize weights
        total = sum(self._weights.values())
        if total > 0:
            for k in self._weights:
                self._weights[k] /= total
        else:
            self._weights = self.DEFAULT_WEIGHTS.copy()

    def calculate(
        self,
        market_state: MarketState,
        market_context: MarketContext,
        timestamp: datetime,
    ) -> ConfidenceState:
        """Calculate confidence score and contribution breakdown, then publish update."""
        factors = {}

        # 1. Trend Factor
        # 1.0 if strong trend (UP/DOWN), 0.3 if SIDEWAYS
        trend_dir = market_state.trend.direction if market_state.trend else TrendDirection.SIDEWAYS
        if trend_dir in (TrendDirection.UP, TrendDirection.DOWN):
            factors["trend_weight"] = 1.0
        else:
            factors["trend_weight"] = 0.3

        # 2. Structure Factor
        # Based on number of confirmed structure points (min 4 for 1.0)
        struct_count = len(market_state.structure_history)
        factors["structure_weight"] = min(1.0, struct_count / 4.0)

        # 3. BOS Factor
        # 1.0 if recent BOS in trend direction, 0.0 otherwise
        bos_factor = 0.0
        if market_state.bos_history and market_state.trend:
            latest_bos = market_state.bos_history[-1]
            if (market_state.trend.direction == TrendDirection.UP and latest_bos.direction == "UP") or \
               (market_state.trend.direction == TrendDirection.DOWN and latest_bos.direction == "DOWN"):
                bos_factor = 1.0
        factors["bos_weight"] = bos_factor

        # 4. CHoCH Factor
        # 0.0 if recent CHoCH (trend reversal signal), 1.0 otherwise
        # We define "recent" as a CHoCH that happened at or after the trend's start_time
        choch_factor = 1.0
        if market_state.choch_history and market_state.trend:
            latest_choch = market_state.choch_history[-1]
            choch_time = latest_choch.trigger_timestamp
            trend_start = market_state.trend.start_time
            if choch_time >= trend_start:
                choch_factor = 0.0
        factors["choch_weight"] = choch_factor

        # 5. Liquidity Factor
        # Based on recently swept levels count
        liq_count = len(market_state.liquidity.swept_levels) if market_state.liquidity else 0
        factors["liquidity_weight"] = min(1.0, liq_count / 3.0)

        # 6. Zone Factor
        # Based on active un-invalidated zones count
        active_zones_count = len([z for z in market_state.zones if not z.is_invalidated])
        factors["zone_weight"] = min(1.0, active_zones_count / 4.0)

        # 7. S&R Factor
        # Based on S&R levels count
        sr_count = len(market_state.sr_levels)
        factors["sr_weight"] = min(1.0, sr_count / 4.0)

        # 8. Volume Factor
        # Normal volume score (expansion=1.0, normal=0.5, climatic=0.3)
        vol_factor = 0.5
        if market_state.volume:
            exp_state = market_state.volume.expansion_state
            if exp_state == VolumeExpansionState.EXPANSION:
                vol_factor = 1.0
            elif exp_state == VolumeExpansionState.CLIMATIC:
                vol_factor = 0.3
        factors["volume_weight"] = vol_factor

        # 9. Session Factor
        # 1.0 if in major session (London/NY), 0.5 otherwise
        session_factor = 0.5
        if market_state.session:
            sess_name = market_state.session.session_name
            if sess_name in (SessionName.LONDON, SessionName.NEW_YORK):
                session_factor = 1.0
        factors["session_weight"] = session_factor

        # 10. Alignment Factor
        # Direct use of alignment_score from MTF engine
        factors["alignment_weight"] = market_context.alignment.alignment_score

        # 11. Regime Factor
        # 1.0 for trending/expansion, 0.5 for ranging, 0.3 for volatile
        regime_factor = 0.5
        regime = market_context.regime
        if regime in (MarketRegime.TRENDING, MarketRegime.EXPANSION):
            regime_factor = 1.0
        elif regime == MarketRegime.VOLATILE:
            regime_factor = 0.3
        factors["regime_weight"] = regime_factor

        # 12. Correlation Factor
        # Mean absolute correlation across tracked pairs
        corr_factor = 0.0
        if market_context.correlation:
            corr_factor = sum(abs(v) for v in market_context.correlation.values()) / len(market_context.correlation)
        factors["correlation_weight"] = corr_factor

        # Calculate final score and contribution breakdown
        score = 0.0
        contribution_breakdown = {}
        for key, weight in self._weights.items():
            factor_val = factors.get(key, 0.0)
            weighted_contrib = factor_val * weight
            score += weighted_contrib
            contribution_breakdown[key] = weighted_contrib

        # Keep score in bounds
        score = max(0.0, min(1.0, score))

        state = ConfidenceState(
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            score=score,
            factors=factors,
            contribution_breakdown=contribution_breakdown,
            timestamp=timestamp,
        )

        # Sprint 5 MarketConfidence Calculations
        confidence_score = score * 100.0
        
        # Heuristics for risk and opportunity
        conflict_score = market_context.alignment.conflict_score if market_context else 0.5
        vol_pct = market_state.volatility_analysis.volatility_percentile if (market_state and market_state.volatility_analysis) else 50.0
        risk_score = min(100.0, max(0.0, (1.0 - score) * 50.0 + vol_pct * 0.3 + conflict_score * 20.0))
        opportunity_score = confidence_score
        
        market_health = "Healthy"
        if score > 0.6:
            market_health = "Healthy"
        elif score > 0.4:
            market_health = "Ranging"
        else:
            market_health = "Unstable"

        pydantic_conf = MarketConfidence(
            symbol=market_state.symbol,
            timeframe=market_state.timeframe,
            confidence_score=confidence_score,
            risk_score=risk_score,
            opportunity_score=opportunity_score,
            market_health=market_health,
            timestamp=timestamp,
        )
        self._pydantic_confidences[(market_state.symbol, market_state.timeframe)] = pydantic_conf

        self._publish_event(state)
        self._publish_confidence_updated(pydantic_conf)
        return state

    def get_pydantic_confidence(self, symbol: str, timeframe: str) -> MarketConfidence | None:
        """Get the current Pydantic MarketConfidence model."""
        return self._pydantic_confidences.get((symbol, timeframe))

    def _publish_event(self, state: ConfidenceState) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": state.symbol,
            "timeframe": state.timeframe,
            "score": state.score,
            "contribution_breakdown": state.contribution_breakdown,
            "timestamp": state.timestamp.isoformat(),
        }

        event = ConfidenceScoreUpdated(
            source="market_intelligence.confidence_engine",
            payload=payload,
        )
        self._event_bus.publish(event)

    def _publish_confidence_updated(self, conf: MarketConfidence) -> None:
        if self._event_bus is None:
            return

        payload = {
            "symbol": conf.symbol,
            "timeframe": conf.timeframe,
            "confidence_score": conf.confidence_score,
            "risk_score": conf.risk_score,
            "opportunity_score": conf.opportunity_score,
            "market_health": conf.market_health,
            "timestamp": conf.timestamp.isoformat(),
        }

        event = MarketConfidenceUpdated(
            source="market_intelligence.confidence_engine",
            payload=payload,
        )
        self._event_bus.publish(event)
