"""Unified Core Analysis Engine for the Market Intelligence Layer."""

from __future__ import annotations

import logging
from typing import Any

from market_intelligence.core.analysis.breakout import BreakEngine
from market_intelligence.core.analysis.state_machine import MarketStateMachine
from market_intelligence.core.analysis.structure import MarketStructureEngine
from market_intelligence.core.analysis.swing import SwingEngine
from market_intelligence.core.analysis.trend import TrendEngine
from market_intelligence.core.analysis.volume import VolumeContextEngine
from market_intelligence.core.analysis.liquidity import LiquidityEngine
from market_intelligence.core.analysis.zone import ZoneEngine
from market_intelligence.core.analysis.sr import SREngine
from market_intelligence.core.analysis.session import SessionEngine
from market_intelligence.core.analysis.mtf import MultiTimeframeEngine
from market_intelligence.core.analysis.regime import MarketRegimeEngine
from market_intelligence.core.analysis.correlation import CorrelationEngine
from market_intelligence.core.analysis.context import MarketContextEngine
from market_intelligence.core.analysis.confidence import ConfidenceEngine
from market_intelligence.core.analysis.story import StoryGenerator
from market_intelligence.core.analysis.volatility import VolatilityEngine
from market_intelligence.core.analysis.order_flow import OrderFlowEngine
from market_intelligence.core.analysis.volume_profile import VolumeProfileEngine

from market_intelligence.core.interfaces import IMarketIntelligenceEngine, IStateStore
from market_intelligence.core.models import MarketState, MarketIntelligence, MarketConfidence, MarketRegime, TrendAnalysis, VolatilityAnalysis, LiquidityAnalysis, OrderFlowAnalysis, VolumeProfileAnalysis, CorrelationAnalysis
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class CoreAnalysisEngine(IMarketIntelligenceEngine):
    """Coordinates all low-level and high-level analytical sub-engines of the MIL."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        k: int = 2,
        state_store: IStateStore | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._k = k
        self._state_store = state_store

        # Sub-engines (Sprint 2 & 3)
        self._swing_engine = SwingEngine(event_bus, k)
        self._structure_engine = MarketStructureEngine(event_bus)
        self._trend_engine = TrendEngine(event_bus)
        self._break_engine = BreakEngine(event_bus)
        self._state_machine = MarketStateMachine()
        self._volume_engine = VolumeContextEngine(event_bus)
        self._liquidity_engine = LiquidityEngine(event_bus)
        self._zone_engine = ZoneEngine(event_bus)
        self._sr_engine = SREngine(event_bus)

        # Sub-engines (Sprint 4)
        self._session_engine = SessionEngine(event_bus)
        self._mtf_engine = MultiTimeframeEngine(state_store, event_bus)
        self._regime_engine = MarketRegimeEngine(event_bus)
        self._correlation_engine = CorrelationEngine(event_bus)
        self._context_engine = MarketContextEngine(event_bus)

        # Sub-engines (Sprint 5)
        self._confidence_engine = ConfidenceEngine(event_bus)
        self._story_generator = StoryGenerator(event_bus)
        self._volatility_engine = VolatilityEngine(event_bus)
        self._order_flow_engine = OrderFlowEngine(event_bus)
        self._volume_profile_engine = VolumeProfileEngine(event_bus)

        # Cache of candle history per (symbol, timeframe)
        self._candle_history: dict[tuple[str, str], list[Any]] = {}

    @property
    def name(self) -> str:
        return "Core Analysis Engine"

    def get_swing_engine(self) -> SwingEngine:
        return self._swing_engine

    def get_structure_engine(self) -> MarketStructureEngine:
        return self._structure_engine

    def get_trend_engine(self) -> TrendEngine:
        return self._trend_engine

    def get_break_engine(self) -> BreakEngine:
        return self._break_engine

    def get_state_machine(self) -> MarketStateMachine:
        return self._state_machine

    def get_volume_engine(self) -> VolumeContextEngine:
        return self._volume_engine

    def get_liquidity_engine(self) -> LiquidityEngine:
        return self._liquidity_engine

    def get_zone_engine(self) -> ZoneEngine:
        return self._zone_engine

    def get_sr_engine(self) -> SREngine:
        return self._sr_engine

    def get_session_engine(self) -> SessionEngine:
        return self._session_engine

    def get_mtf_engine(self) -> MultiTimeframeEngine:
        return self._mtf_engine

    def get_regime_engine(self) -> MarketRegimeEngine:
        return self._regime_engine

    def get_correlation_engine(self) -> CorrelationEngine:
        return self._correlation_engine

    def get_context_engine(self) -> MarketContextEngine:
        return self._context_engine

    def get_confidence_engine(self) -> ConfidenceEngine:
        return self._confidence_engine

    def get_story_generator(self) -> StoryGenerator:
        return self._story_generator

    def analyze(self, snapshot: Any) -> Any:
        """Process a market snapshot. (Contract implementation).

        Normally, we iterate over all states inside the snapshot and process them.
        For a single candle, we use analyze_candle.
        """
        return snapshot

    def analyze_candle(self, candle: Any) -> MarketState:
        """Process a single incoming OHLCV candle, driving the entire analytical pipeline.

        Returns the updated MarketState.
        """
        symbol = candle.symbol
        timeframe = candle.interval
        key = (symbol, timeframe)

        if key not in self._candle_history:
            self._candle_history[key] = []

        history = self._candle_history[key]
        prev_candle = history[-1] if history else None
        history.append(candle)

        # Pipeline Sequence:
        
        # 1. Volume
        vol_state = self._volume_engine.process_candle(candle)
        atr = self._volume_engine.get_atr(symbol, timeframe)

        # 2. Swings
        swing = self._swing_engine.process_candle(candle)

        # 3. Structure
        if swing is not None:
            self._structure_engine.process_swing(swing)
            self._liquidity_engine.register_swing(swing)

        # 4. Trend
        struct_history = self._structure_engine.get_structure_history(
            symbol, timeframe
        )
        self._trend_engine.evaluate_trend(
            symbol, timeframe, struct_history, candle.timestamp, candle
        )
        trend_direction = self._trend_engine.get_trend_direction(
            symbol, timeframe
        )

        # 5. Breakout
        bos, choch = self._break_engine.evaluate_breakouts(
            symbol, timeframe, trend_direction, struct_history, candle
        )

        # State machine transitions
        self._state_machine.update_state(
            symbol,
            timeframe,
            trend_direction,
            struct_history,
            bos,
            choch,
            candle,
            prev_candle,
        )
        market_phase_state = self._state_machine.get_state(symbol, timeframe)

        # 6. Liquidity
        liq_state = self._liquidity_engine.evaluate_sweeps(
            symbol, timeframe, candle, vol_state.normalized_volume
        )

        # 7. Zones
        zones = self._zone_engine.evaluate_zones(
            symbol, timeframe, history, atr
        )

        # 8. Support/Resistance
        all_swings = self._swing_engine.get_swings(symbol, timeframe)
        sr_levels = self._sr_engine.evaluate_levels(
            symbol, timeframe, all_swings, history, atr
        )

        # 9. Session
        session_state = self._session_engine.process_candle(candle)

        # 10. Multi-Timeframe
        alignment = self._mtf_engine.process_alignment(
            symbol, timeframe, trend_direction, candle.timestamp
        )

        # 11. Regime
        regime = self._regime_engine.process_regime(
            symbol,
            timeframe,
            vol_state,
            atr,
            trend_direction,
            market_phase_state,
            candle.timestamp,
        )

        # 12. Correlation
        correlation = self._correlation_engine.process_correlation(
            symbol, timeframe, candle
        )

        # --- Sprint 5 new engine executions ---
        volatility_analysis = self._volatility_engine.calculate_volatility(candle)
        order_flow_analysis = self._order_flow_engine.calculate_order_flow(candle)
        volume_profile_analysis = self._volume_profile_engine.calculate_volume_profile(candle)

        # Fetch Pydantic model outputs from engines
        regime_analysis = self._regime_engine.get_pydantic_regime(symbol, timeframe)
        trend_analysis = self._trend_engine.get_pydantic_trend(symbol, timeframe)
        liquidity_analysis = self._liquidity_engine.get_pydantic_liquidity(symbol, timeframe)
        correlation_analysis = self._correlation_engine.get_pydantic_correlation(symbol, timeframe)

        # 13. Market Context
        market_context = self._context_engine.process_context(
            symbol=symbol,
            timeframe=timeframe,
            dominant_trend=alignment.dominant_trend,
            session_state=session_state,
            regime=regime,
            alignment=alignment,
            liquidity=liq_state,
            active_zones=zones,
            volume_state=vol_state,
            correlation=correlation,
            sr_levels=sr_levels,
            timestamp=candle.timestamp,
        )

        # 14. MarketState
        state = MarketState(
            symbol=symbol,
            timeframe=timeframe,
            swings=all_swings,
            trend=self._trend_engine.get_trend_state(symbol, timeframe),
            liquidity=liq_state,
            zones=zones,
            session=session_state,
            volume=vol_state,
            sr_levels=sr_levels,
            structure_history=struct_history,
            bos_history=self._break_engine.get_bos_history(symbol, timeframe),
            choch_history=self._break_engine.get_choch_history(symbol, timeframe),
            market_phase_state=market_phase_state,
            market_context=market_context,
            
            # Sprint 5 Analysis outputs
            regime_analysis=regime_analysis,
            trend_analysis=trend_analysis,
            volatility_analysis=volatility_analysis,
            liquidity_analysis=liquidity_analysis,
            order_flow_analysis=order_flow_analysis,
            volume_profile_analysis=volume_profile_analysis,
            correlation_analysis=correlation_analysis,
            
            updated_at=candle.timestamp,
        )

        # 15. Confidence
        confidence = None
        if market_context is not None:
            confidence = self._confidence_engine.calculate(
                state, market_context, candle.timestamp
            )

        market_confidence = self._confidence_engine.get_pydantic_confidence(symbol, timeframe)

        # 16. Story
        story = None
        if market_context is not None and confidence is not None:
            story = self._story_generator.generate(
                state, market_context, confidence, candle.timestamp
            )

        # 17. MarketIntelligence completed package
        market_intelligence = None
        if (
            regime_analysis and trend_analysis and volatility_analysis and
            liquidity_analysis and order_flow_analysis and volume_profile_analysis and
            correlation_analysis and market_confidence
        ):
            market_intelligence = MarketIntelligence(
                symbol=symbol,
                timeframe=timeframe,
                regime=regime_analysis,
                trend=trend_analysis,
                volatility=volatility_analysis,
                liquidity=liquidity_analysis,
                order_flow=order_flow_analysis,
                volume_profile=volume_profile_analysis,
                correlation=correlation_analysis,
                confidence=market_confidence,
                timestamp=candle.timestamp,
            )

        # Final enrichment
        state = state.model_copy(
            update={
                "confidence": confidence,
                "story": story,
                "market_confidence": market_confidence,
                "market_intelligence": market_intelligence,
            }
        )

        return state

