"""Price Action Orchestrator managing pipeline execution, detection engines, feature storage, and event bus broadcasts."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from market_intelligence.core.models import MarketState
from price_action.analysis.fvg_detector import FairValueGapDetector
from price_action.analysis.liquidity_engine import LiquidityEngine
from price_action.analysis.market_regime_engine import MarketRegimeEngine
from price_action.analysis.market_structure_detector import MarketStructureDetector
from price_action.analysis.momentum_engine import MomentumEngine
from price_action.analysis.multi_timeframe_aggregator import MultiTimeframeAggregator
from price_action.analysis.order_block_detector import OrderBlockDetector
from price_action.analysis.pattern_engine import PatternEngine
from price_action.analysis.premium_discount_engine import PremiumDiscountEngine
from price_action.analysis.swing_detector import SwingDetector
from price_action.analysis.trend_engine import TrendEngine
from price_action.analysis.volatility_engine import VolatilityEngine
from price_action.core.enums import PatternStatus
from price_action.core.events import (
    PatternCompleted,
    PatternConfirmed,
    PatternDetected,
    PatternInvalidated,
    PatternQualityUpdated,
    PatternUpdated,
    PriceActionAnalysisCompleted,
    PriceActionFailed,
    PriceActionGenerated,
    PriceActionUpdated,
)
from price_action.core.exceptions import OrchestratorError
from price_action.core.feature_store import PriceActionFeatureStore
from price_action.core.interfaces import (
    IFairValueGapDetector,
    ILiquidityEngine,
    IMarketRegimeEngine,
    IMarketStructureDetector,
    IMomentumEngine,
    IMultiTimeframeAggregator,
    IOrderBlockDetector,
    IPatternRepository,
    IPatternStateStore,
    IPremiumDiscountEngine,
    IPriceActionFeatureStore,
    ISwingDetector,
    ITrendEngine,
    IVolatilityEngine,
)
from price_action.core.models import (
    MultiTimeframePriceActionSnapshot,
    PatternCandidate,
    PatternMatch,
    PatternSnapshot,
    PatternState,
    PriceActionBar,
    PriceActionConfig,
    TimeframePriceActionSnapshot,
)
from price_action.quality.quality_engine import PatternQualityEngine
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class PriceActionOrchestrator:
    """Coordinates price action detection engines, feature store, state storage, persistence, and event bus broadcasts."""

    def __init__(self) -> None:
        self._pattern_engine: PatternEngine | None = None
        self._state_store: IPatternStateStore | None = None
        self._repository: IPatternRepository | None = None
        self._event_bus: IEventBus | None = None
        self._container: IContainer | None = None
        self._quality_engine: PatternQualityEngine | None = None
        self._feature_store: IPriceActionFeatureStore | None = None

        # Sprint 5 Detection Engines
        self._swing_detector: ISwingDetector = SwingDetector()
        self._structure_detector: IMarketStructureDetector = MarketStructureDetector()
        self._trend_engine: ITrendEngine = TrendEngine()
        self._volatility_engine: IVolatilityEngine = VolatilityEngine()
        self._momentum_engine: IMomentumEngine = MomentumEngine()
        self._liquidity_engine: ILiquidityEngine = LiquidityEngine()
        self._fvg_detector: IFairValueGapDetector = FairValueGapDetector()
        self._ob_detector: IOrderBlockDetector = OrderBlockDetector()
        self._pd_engine: IPremiumDiscountEngine = PremiumDiscountEngine()
        self._regime_engine: IMarketRegimeEngine = MarketRegimeEngine()
        self._mtf_aggregator: IMultiTimeframeAggregator = MultiTimeframeAggregator()

    def initialize(
        self,
        pattern_engine: PatternEngine | None = None,
        state_store: IPatternStateStore | None = None,
        repository: IPatternRepository | None = None,
        event_bus: IEventBus | None = None,
        container: IContainer | None = None,
        quality_engine: PatternQualityEngine | None = None,
        feature_store: IPriceActionFeatureStore | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._pattern_engine = pattern_engine or PatternEngine()
        self._state_store = state_store
        self._repository = repository
        self._event_bus = event_bus
        self._container = container
        self._feature_store = feature_store or PriceActionFeatureStore()

        if container is not None:
            if container.has(PatternQualityEngine):
                self._quality_engine = container.resolve(PatternQualityEngine)
            else:
                self._quality_engine = quality_engine or PatternQualityEngine()

            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
        else:
            self._quality_engine = quality_engine or PatternQualityEngine()

        if self._pattern_engine is not None:
            self._pattern_engine.set_container(container)

    def process_candles(
        self,
        symbol: str,
        timeframe: str,
        bars: List[PriceActionBar],
        config: Optional[PriceActionConfig] = None,
    ) -> TimeframePriceActionSnapshot:
        """Run single-timeframe price action analysis pipeline over candle bars."""
        cfg = config or PriceActionConfig()

        if not bars:
            logger.info("PriceActionOrchestrator: Empty bar list for '%s' (%s). Returning empty snapshot.", symbol, timeframe)
            return TimeframePriceActionSnapshot(symbol=symbol, timeframe=timeframe)

        try:
            # 1. Swing Detection
            swings = self._swing_detector.detect_swings(bars, cfg)

            # 2. Market Structure Analysis
            market_struct = self._structure_detector.detect_market_structure(bars, swings, cfg)

            # 3. Trend Analysis
            trend_metrics = self._trend_engine.analyze_trend(bars, cfg)

            # 4. Volatility Analysis
            volatility_metrics = self._volatility_engine.analyze_volatility(bars, cfg)

            # 5. Momentum Analysis
            momentum_metrics = self._momentum_engine.analyze_momentum(bars, swings, cfg)

            # 6. Liquidity Pool Detection
            liquidity_pools = self._liquidity_engine.detect_liquidity(bars, swings, cfg)

            # 7. Fair Value Gap Detection
            fvgs = self._fvg_detector.detect_fvgs(bars, cfg)

            # 8. Order Block Detection
            order_blocks = self._ob_detector.detect_order_blocks(bars, swings, cfg)

            # 9. Premium / Discount Zone Calculation
            curr_price = bars[-1].close if bars else 0.0
            pd_state = self._pd_engine.calculate_zones(curr_price, swings, cfg)

            # 10. Macro Market Regime Classification
            regime_state = self._regime_engine.classify_regime(trend_metrics, volatility_metrics, market_struct, cfg)

            tf_snapshot = TimeframePriceActionSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.now(timezone.utc),
                swings=swings,
                market_structure=market_struct,
                trend=trend_metrics,
                volatility=volatility_metrics,
                momentum=momentum_metrics,
                liquidity_pools=liquidity_pools,
                fvgs=fvgs,
                order_blocks=order_blocks,
                premium_discount=pd_state,
                regime=regime_state,
            )

            # Dispatch PriceActionUpdated event
            if self._event_bus is not None:
                self._event_bus.publish(
                    PriceActionUpdated(
                        source="price_action.orchestrator",
                        payload={"symbol": symbol, "timeframe": timeframe, "snapshot": tf_snapshot.model_dump(mode="json")},
                    )
                )

            return tf_snapshot

        except Exception as e:
            logger.error("PriceActionOrchestrator: Exception during candle processing for '%s': %s. Failing closed.", symbol, e, exc_info=True)
            if self._event_bus is not None:
                self._event_bus.publish(
                    PriceActionFailed(
                        source="price_action.orchestrator",
                        payload={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
                    )
                )
            return TimeframePriceActionSnapshot(symbol=symbol, timeframe=timeframe)

    def process_multi_timeframe(
        self,
        symbol: str,
        timeframe_bars: Dict[str, List[PriceActionBar]],
        config: Optional[PriceActionConfig] = None,
    ) -> MultiTimeframePriceActionSnapshot:
        """Run multi-timeframe price action analysis pipeline across multiple timeframes."""
        cfg = config or PriceActionConfig()

        if not timeframe_bars:
            logger.info("PriceActionOrchestrator: Empty multi-timeframe dict for '%s'. Returning empty MTF snapshot.", symbol)
            return MultiTimeframePriceActionSnapshot(symbol=symbol)

        try:
            tf_snapshots: Dict[str, TimeframePriceActionSnapshot] = {}
            for tf, bars in timeframe_bars.items():
                tf_snapshots[tf] = self.process_candles(symbol, tf, bars, cfg)

            mtf_snapshot = self._mtf_aggregator.aggregate_snapshots(symbol, tf_snapshots)

            # Store in FeatureStore
            if self._feature_store is not None:
                self._feature_store.store_snapshot(mtf_snapshot)

            # Dispatch events
            if self._event_bus is not None:
                self._event_bus.publish(
                    PriceActionGenerated(
                        source="price_action.orchestrator",
                        payload={"symbol": symbol, "mtf_snapshot": mtf_snapshot.model_dump(mode="json")},
                    )
                )
                self._event_bus.publish(
                    PriceActionAnalysisCompleted(
                        source="price_action.orchestrator",
                        payload={"symbol": symbol, "snapshot_id": mtf_snapshot.snapshot_id},
                    )
                )

            return mtf_snapshot

        except Exception as e:
            logger.error("PriceActionOrchestrator: Exception during MTF processing for '%s': %s. Failing closed.", symbol, e, exc_info=True)
            if self._event_bus is not None:
                self._event_bus.publish(
                    PriceActionFailed(
                        source="price_action.orchestrator",
                        payload={"symbol": symbol, "error": str(e)},
                    )
                )
            return MultiTimeframePriceActionSnapshot(symbol=symbol)

    def process_market_state(self, market_state: MarketState) -> PatternState:
        """Run pattern recognition pipeline for a given MarketState (backward compatibility)."""
        if not self._pattern_engine or not self._state_store:
            raise OrchestratorError("Orchestrator is not initialized.")

        symbol = market_state.symbol
        timeframe = market_state.timeframe

        try:
            # 1. Fetch previous timeframe state for transition alerts
            prev_snapshot = self._state_store.get_snapshot(symbol)
            prev_state = prev_snapshot.states.get(timeframe) if prev_snapshot else None

            # 2. Run pluggable pattern detection engine
            engine_state = self._pattern_engine.run(market_state)

            # 3. Consolidate and transition pattern lifecycles
            new_active_patterns: list[PatternMatch] = list(engine_state.active_patterns)
            new_historical_patterns: list[PatternMatch] = list(engine_state.historical_patterns)

            if prev_state:
                new_historical_patterns.extend(prev_state.historical_patterns)

            latest_swing = market_state.swings[-1] if market_state.swings else None
            active_ids: set[str] = {m.match_id for m in new_active_patterns}

            if prev_state and latest_swing:
                for pattern in prev_state.active_patterns:
                    if pattern.match_id in active_ids:
                        continue

                    high_prices = [p.price for p in pattern.points]
                    low_prices = [p.price for p in pattern.points]
                    if not high_prices:
                        new_active_patterns.append(pattern)
                        active_ids.add(pattern.match_id)
                        continue

                    pattern_max = max(high_prices)
                    pattern_min = min(low_prices)

                    # Invalidation and completion logic
                    pattern_height = pattern_max - pattern_min
                    if pattern.direction.value == "BULLISH" and latest_swing.price < pattern_min:
                        invalidated_pattern = pattern.model_copy(
                            update={"status": PatternStatus.INVALIDATED, "invalidated_at": market_state.updated_at}
                        )
                        new_historical_patterns.append(invalidated_pattern)
                    elif pattern.direction.value == "BEARISH" and latest_swing.price > pattern_max:
                        invalidated_pattern = pattern.model_copy(
                            update={"status": PatternStatus.INVALIDATED, "invalidated_at": market_state.updated_at}
                        )
                        new_historical_patterns.append(invalidated_pattern)
                    elif pattern.direction.value == "BULLISH" and latest_swing.price >= (pattern_max + pattern_height):
                        completed_pattern = pattern.model_copy(
                            update={"status": PatternStatus.COMPLETED, "completed_at": market_state.updated_at}
                        )
                        new_historical_patterns.append(completed_pattern)
                    elif pattern.direction.value == "BEARISH" and latest_swing.price <= (pattern_min - pattern_height):
                        completed_pattern = pattern.model_copy(
                            update={"status": PatternStatus.COMPLETED, "completed_at": market_state.updated_at}
                        )
                        new_historical_patterns.append(completed_pattern)
                    else:
                        new_active_patterns.append(pattern)
                        active_ids.add(pattern.match_id)

            processed_candidates: list[PatternCandidate] = []
            for cand in engine_state.candidate_patterns:
                quality = None
                if self._quality_engine is not None:
                    try:
                        if hasattr(self._quality_engine, "evaluate_candidate"):
                            quality = self._quality_engine.evaluate_candidate(cand, market_state)
                        elif hasattr(self._quality_engine, "evaluate"):
                            quality = self._quality_engine.evaluate(cand, market_state)
                    except Exception as q_err:
                        logger.warning("PriceActionOrchestrator: Quality score evaluation failed for %s: %s", cand.candidate_id, q_err)

                cand_with_quality = cand.model_copy(update={"quality": quality}) if quality else cand
                processed_candidates.append(cand_with_quality)

            pattern_state = PatternState(
                symbol=symbol,
                timeframe=timeframe,
                active_patterns=new_active_patterns,
                candidate_patterns=processed_candidates,
                historical_patterns=new_historical_patterns,
                updated_at=market_state.updated_at,
            )

            # 4. Update in-memory state store
            updated_snapshot = self._state_store.update_timeframe_state(symbol, timeframe, pattern_state)

            # 5. Persist to repository
            if self._repository is not None:
                self._repository.save_snapshot(updated_snapshot)

            # 6. Dispatch transition events
            self._dispatch_events(prev_state, pattern_state)

            # Safely publish PriceActionCompleted event if EventBus is configured
            if self._event_bus is not None:
                from toji_platform.core.event_bus.events import PriceActionCompleted
                pac_event = PriceActionCompleted(
                    source="price_action.orchestrator",
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "state": pattern_state.model_dump(mode="json"),
                    },
                )
                self._event_bus.publish(pac_event)

            return pattern_state

        except Exception as e:
            logger.error("PriceActionOrchestrator: Execution failed: %s", e)
            if self._event_bus is not None:
                self._event_bus.publish(
                    PriceActionFailed(
                        source="price_action.orchestrator",
                        payload={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
                    )
                )
            raise OrchestratorError(f"Failed to process market state: {e}") from e

    def _dispatch_events(self, prev_state: PatternState | None, curr_state: PatternState) -> None:
        """Analyze differences between states and publish transition events."""
        if self._event_bus is None:
            return

        symbol = curr_state.symbol
        timeframe = curr_state.timeframe
        source = "price_action.orchestrator"

        prev_candidates = {c.candidate_id: c for c in prev_state.candidate_patterns} if prev_state else {}
        prev_matches = {}
        if prev_state:
            for m in prev_state.active_patterns + prev_state.historical_patterns:
                prev_matches[m.match_id] = m

        active_match_ids = {m.match_id for m in curr_state.active_patterns}
        for candidate in curr_state.candidate_patterns:
            cid = candidate.candidate_id
            payload = {
                "symbol": symbol,
                "timeframe": timeframe,
                "candidate": candidate.model_dump(mode="json"),
            }

            if cid not in prev_candidates:
                self._event_bus.publish(PatternDetected(source=source, payload=payload))
            else:
                prev_c = prev_candidates[cid]
                if prev_c.score != candidate.score or len(prev_c.points) != len(candidate.points):
                    upd_payload = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "pattern_id": cid,
                        "status": "DEVELOPING",
                        "pattern": candidate.model_dump(mode="json"),
                    }
                    self._event_bus.publish(PatternUpdated(source=source, payload=upd_payload))

            # Dispatch PatternQualityUpdated for candidate if quality present and not promoted to active match
            if candidate.quality is not None and cid not in active_match_ids:
                prev_c = prev_candidates.get(cid)
                if not prev_c or not prev_c.quality or prev_c.quality.overall_score != candidate.quality.overall_score:
                    q_payload = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "pattern_id": cid,
                        "status": "DEVELOPING",
                        "quality": candidate.quality.model_dump(mode="json"),
                    }
                    self._event_bus.publish(PatternQualityUpdated(source=source, payload=q_payload))

        curr_matches = curr_state.active_patterns + curr_state.historical_patterns
        for match in curr_matches:
            mid = match.match_id
            status_val = match.status.value
            match_json = match.model_dump(mode="json")
            payload = {"symbol": symbol, "timeframe": timeframe, "match": match_json}

            if mid not in prev_matches:
                if match.status == PatternStatus.CONFIRMED:
                    self._event_bus.publish(PatternConfirmed(source=source, payload=payload))
                elif match.status == PatternStatus.INVALIDATED:
                    self._event_bus.publish(PatternInvalidated(source=source, payload=payload))
                elif match.status == PatternStatus.COMPLETED:
                    self._event_bus.publish(PatternCompleted(source=source, payload=payload))
            else:
                prev_m = prev_matches[mid]
                if prev_m.status != match.status:
                    if match.status == PatternStatus.CONFIRMED:
                        self._event_bus.publish(PatternConfirmed(source=source, payload=payload))
                    elif match.status == PatternStatus.INVALIDATED:
                        self._event_bus.publish(PatternInvalidated(source=source, payload=payload))
                    elif match.status == PatternStatus.COMPLETED:
                        self._event_bus.publish(PatternCompleted(source=source, payload=payload))

            # Dispatch PatternQualityUpdated for match
            if match.quality is not None:
                prev_m = prev_matches.get(mid)
                if not prev_m or not prev_m.quality or prev_m.quality.overall_score != match.quality.overall_score:
                    q_payload = {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "pattern_id": mid,
                        "status": status_val,
                        "quality": match.quality.model_dump(mode="json"),
                    }
                    self._event_bus.publish(PatternQualityUpdated(source=source, payload=q_payload))

    @property
    def feature_store(self) -> IPriceActionFeatureStore | None:
        return self._feature_store
