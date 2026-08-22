"""Market Regime Engine for classifying market regimes using deterministic rules."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.enums import MarketRegime as MarketRegimeEnum, TrendDirection, VolumeExpansionState
from market_intelligence.core.events import MarketRegimeChanged, MarketRegimeDetected
from market_intelligence.core.models import VolumeState, MarketRegime as MarketRegimeModel
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class MarketRegimeEngine:
    """Classifies the market regime using deterministic rules based on price volatility and volume."""

    def __init__(self, event_bus: IEventBus | None = None) -> None:
        self._event_bus = event_bus
        # Mapping: (symbol, timeframe) -> list of ATR values
        self._atr_history: dict[tuple[str, str], list[float]] = {}
        # Mapping: (symbol, timeframe) -> last classified MarketRegimeEnum
        self._last_regime: dict[tuple[str, str], MarketRegimeEnum] = {}
        # Mapping: (symbol, timeframe) -> Pydantic MarketRegime model
        self._pydantic_regimes: dict[tuple[str, str], MarketRegimeModel] = {}

    def process_regime(
        self,
        symbol: str,
        timeframe: str,
        volume_state: VolumeState | None,
        atr: float,
        trend_direction: TrendDirection,
        market_phase_state: str,
        timestamp: Any,
    ) -> MarketRegimeEnum:
        """Classify the current market regime and publish events on changes."""
        key = (symbol, timeframe)
        if key not in self._atr_history:
            self._atr_history[key] = []

        atr_hist = self._atr_history[key]
        atr_hist.append(atr)
        if len(atr_hist) > 100:
            atr_hist.pop(0)

        # 1. Determine local indicators
        is_atr_declining = len(atr_hist) > 1 and atr < atr_hist[-2]

        is_volatile = False
        is_expansion = False
        is_contraction = False

        if volume_state is not None:
            if volume_state.expansion_state == VolumeExpansionState.CLIMATIC:
                is_volatile = True
            elif volume_state.expansion_state == VolumeExpansionState.EXPANSION or volume_state.normalized_volume > 1.5:
                is_expansion = True
            elif volume_state.normalized_volume < 0.8 and is_atr_declining:
                is_contraction = True

        # Check volatility using ATR relative to its rolling MA (20 periods)
        window = min(len(atr_hist), 20)
        mean_atr = 0.0
        if window > 0:
            mean_atr = sum(atr_hist[-window:]) / window
            if mean_atr > 0.0 and atr > 1.5 * mean_atr:
                is_volatile = True

        # 2. Priority Classification
        if is_volatile:
            regime = MarketRegimeEnum.VOLATILE
        elif is_expansion:
            regime = MarketRegimeEnum.EXPANSION
        elif is_contraction:
            regime = MarketRegimeEnum.CONTRACTION
        elif market_phase_state == "Accumulation":
            regime = MarketRegimeEnum.ACCUMULATION
        elif market_phase_state == "Distribution":
            regime = MarketRegimeEnum.DISTRIBUTION
        elif trend_direction in (TrendDirection.UP, TrendDirection.DOWN):
            regime = MarketRegimeEnum.TRENDING
        else:
            regime = MarketRegimeEnum.RANGING

        # Calculate metrics for the Pydantic model
        volatility_level = (atr / mean_atr) if mean_atr > 0.0 else 1.0
        trend_strength = 1.0 if trend_direction in (TrendDirection.UP, TrendDirection.DOWN) else 0.3
        
        # Simple heuristic for confidence (0.0 to 1.0)
        confidence = 0.6
        if regime in (MarketRegimeEnum.TRENDING, MarketRegimeEnum.EXPANSION) and trend_strength > 0.5:
            confidence = 0.85
        elif regime == MarketRegimeEnum.VOLATILE:
            confidence = 0.70

        pydantic_model = MarketRegimeModel(
            symbol=symbol,
            timeframe=timeframe,
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility_level=volatility_level,
            timestamp=timestamp,
        )
        self._pydantic_regimes[key] = pydantic_model

        # 3. Check for transition and publish event
        prev_regime = self._last_regime.get(key)
        if prev_regime != regime:
            self._last_regime[key] = regime
            self._publish_change_event(symbol, timeframe, prev_regime, regime, timestamp)
            self._publish_detected_event(pydantic_model)

        return regime

    def get_regime(self, symbol: str, timeframe: str) -> MarketRegimeEnum:
        """Get the current regime enum or return RANGING as default."""
        return self._last_regime.get((symbol, timeframe), MarketRegimeEnum.RANGING)

    def get_pydantic_regime(self, symbol: str, timeframe: str) -> MarketRegimeModel | None:
        """Get the current Pydantic MarketRegime model."""
        return self._pydantic_regimes.get((symbol, timeframe))

    def _publish_change_event(
        self,
        symbol: str,
        timeframe: str,
        old_regime: MarketRegime | None,
        new_regime: MarketRegime,
        timestamp: Any,
    ) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "old_regime": old_regime.value if old_regime else None,
            "new_regime": new_regime.value,
            "timestamp": timestamp.isoformat(),
        }
        event = MarketRegimeChanged(
            source="market_intelligence.regime_engine",
            payload=payload,
        )
        self._event_bus.publish(event)

    def _publish_detected_event(self, analysis: MarketRegimeModel) -> None:
        if self._event_bus is None:
            return
        payload = {
            "symbol": analysis.symbol,
            "timeframe": analysis.timeframe,
            "regime": analysis.regime.value,
            "confidence": analysis.confidence,
            "trend_strength": analysis.trend_strength,
            "volatility_level": analysis.volatility_level,
            "timestamp": analysis.timestamp.isoformat()
        }
        event = MarketRegimeDetected(
            source="market_intelligence.regime_engine",
            payload=payload
        )
        self._event_bus.publish(event)
