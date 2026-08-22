"""Market Intelligence Orchestrator for coordinating all MIL sub-engines."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.analysis.confidence import ConfidenceEngine
from market_intelligence.core.analysis.engine import CoreAnalysisEngine
from market_intelligence.core.analysis.story import StoryGenerator
from market_intelligence.core.enums import HealthState, ReplayStatus
from market_intelligence.core.events import (
    ConfidenceScoreUpdated,
    MarketStoryGenerated,
    MarketStateUpdated,
)
from market_intelligence.core.exceptions import OrchestratorError
from market_intelligence.core.health import HealthMonitor
from market_intelligence.core.interfaces import IRepository, IStateStore
from market_intelligence.core.models import (
    HealthReport,
    MarketSnapshot,
    MarketState,
)
from market_intelligence.core.performance import PerformanceMonitor
from market_intelligence.core.state import MarketIntelligenceState
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class MarketIntelligenceOrchestrator:
    """Coordinates the execution of CoreAnalysisEngine, ConfidenceEngine, and StoryGenerator.

    Provides a single unified entry point for both streaming data and replay validation.
    """

    def __init__(
        self,
        engine: CoreAnalysisEngine,
        confidence_engine: ConfidenceEngine,
        story_generator: StoryGenerator,
        event_bus: IEventBus | None = None,
        state_store: IStateStore | None = None,
        repository: IRepository | None = None,
        health_monitor: HealthMonitor | None = None,
        performance_monitor: PerformanceMonitor | None = None,
    ) -> None:
        self._engine = engine
        self._confidence_engine = confidence_engine
        self._story_generator = story_generator
        self._event_bus = event_bus
        self._state_store = state_store
        self._repository = repository

        self._health_monitor = health_monitor or HealthMonitor(event_bus)
        self._performance_monitor = performance_monitor or PerformanceMonitor()

    def process_candle(self, candle: Any) -> MarketState:
        """Streaming mode: process one candle through the full pipeline."""
        start_time = time.perf_counter()
        symbol = candle.symbol
        timeframe = candle.interval

        try:
            # 1. Core analysis
            try:
                state = self._engine.analyze_candle(candle)
                self._health_monitor.set_engine_status("core_analysis_engine", HealthState.HEALTHY)
            except Exception as e:
                logger.error("CoreAnalysisEngine failed to analyze candle: %s", e)
                self._health_monitor.set_engine_status("core_analysis_engine", HealthState.FAILED)
                raise OrchestratorError(f"Core analysis failed: {e}") from e

            # Get or create active snapshot for context references
            if self._state_store is not None:
                snapshot = self._state_store.get_snapshot(symbol)
                if snapshot is None:
                    snapshot = MarketSnapshot(
                        snapshot_id=str(uuid.uuid4()),
                        symbol=symbol,
                        timestamp=candle.timestamp,
                        states={},
                    )
                    self._state_store.update_snapshot(snapshot)

                # Temporarily store intermediate state in the store so engines can query it
                self._state_store.update_timeframe_state(
                    symbol=symbol,
                    timeframe=timeframe,
                    state_update=state,
                )

            # 2. Confidence Score
            confidence = None
            if state.market_context is not None:
                try:
                    confidence = self._confidence_engine.calculate(
                        state, state.market_context, candle.timestamp
                    )
                    self._health_monitor.set_engine_status("confidence_engine", HealthState.HEALTHY)
                    self._performance_monitor.record_event_published()
                except Exception as e:
                    logger.error("ConfidenceEngine calculation failed: %s", e)
                    self._health_monitor.set_engine_status("confidence_engine", HealthState.DEGRADED)

            # 3. Story Generation
            story = None
            if state.market_context is not None and confidence is not None:
                try:
                    story = self._story_generator.generate(
                        state, state.market_context, confidence, candle.timestamp
                    )
                    self._health_monitor.set_engine_status("story_generator", HealthState.HEALTHY)
                    self._performance_monitor.record_event_published()
                except Exception as e:
                    logger.error("StoryGenerator generation failed: %s", e)
                    self._health_monitor.set_engine_status("story_generator", HealthState.DEGRADED)

            # 4. Enrich MarketState with confidence and story
            enriched_state = state.model_copy(
                update={
                    "confidence": confidence,
                    "story": story,
                }
            )

            # 5. Update state store with final enriched state
            if self._state_store is not None:
                updated_snapshot = self._state_store.update_timeframe_state(
                    symbol=symbol,
                    timeframe=timeframe,
                    state_update=enriched_state,
                )

                # 6. Persist through repository
                if self._repository is not None:
                    try:
                        self._repository.save_snapshot(updated_snapshot)
                    except Exception as e:
                        logger.error("Failed to save snapshot to repository: %s", e)
                        self._health_monitor.add_dependency_failure("repository")

            # 7. Record performance metrics
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            self._performance_monitor.record_candle_processed(latency_ms)
            self._health_monitor.set_processing_latency(latency_ms)

            # Publish MarketStateUpdated
            self._publish_state_event(enriched_state)
            self._performance_monitor.record_event_published()

            return enriched_state

        except Exception as e:
            logger.error("Orchestrator failed to process candle: %s", e)
            raise

    def replay(self, candles: list[Any]) -> list[MarketState]:
        """Replay mode: process historical candle sequence in isolation."""
        if not candles:
            return []

        # Create isolated temporary store and engine to ensure replay determinism
        temp_state_store = MarketIntelligenceState()
        temp_engine = CoreAnalysisEngine(
            event_bus=None,
            k=self._engine._k,
            state_store=temp_state_store,
        )
        temp_confidence = ConfidenceEngine(event_bus=None)
        temp_story = StoryGenerator(event_bus=None)

        replayed_states = []
        for candle in candles:
            symbol = candle.symbol
            timeframe = candle.interval

            state = temp_engine.analyze_candle(candle)

            snapshot = temp_state_store.get_snapshot(symbol)
            if snapshot is None:
                snapshot = MarketSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=candle.timestamp,
                    states={},
                )
                temp_state_store.update_snapshot(snapshot)

            temp_state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=state,
            )

            confidence = None
            if state.market_context is not None:
                confidence = temp_confidence.calculate(
                    state, state.market_context, candle.timestamp
                )

            story = None
            if state.market_context is not None and confidence is not None:
                story = temp_story.generate(
                    state, state.market_context, confidence, candle.timestamp
                )

            enriched_state = state.model_copy(
                update={
                    "confidence": confidence,
                    "story": story,
                }
            )
            replayed_states.append(enriched_state)

            temp_state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=enriched_state,
            )

        return replayed_states

    def get_health(self) -> HealthReport:
        """Report health status of all engines."""
        return self._health_monitor.get_report()

    def shutdown(self) -> None:
        """Graceful shutdown of orchestrator monitoring resources."""
        logger.info("Shutting down Market Intelligence Orchestrator...")
        self._performance_monitor.reset()

    def restart(self) -> None:
        """Clear state and reinitialize engines."""
        logger.info("Restarting Market Intelligence Orchestrator...")
        if self._state_store is not None:
            self._state_store.clear()
        self._engine = CoreAnalysisEngine(
            event_bus=self._event_bus,
            k=self._engine._k,
            state_store=self._state_store,
        )
        self._performance_monitor.reset()
        self._health_monitor.clear_dependency_failures()
        self._health_monitor.set_replay_status(ReplayStatus.PENDING)

    def _publish_state_event(self, state: MarketState) -> None:
        if self._event_bus is None:
            return

        event = MarketStateUpdated(
            source="market_intelligence.orchestrator",
            payload={
                "symbol": state.symbol,
                "timeframe": state.timeframe,
                "state": state.model_dump(mode="json"),
            },
        )
        self._event_bus.publish(event)

        # Publish MarketIntelligenceCompleted event for the pipeline
        from toji_platform.core.event_bus.events import MarketIntelligenceCompleted
        mic_event = MarketIntelligenceCompleted(
            source="market_intelligence.orchestrator",
            payload={
                "symbol": state.symbol,
                "timeframe": state.timeframe,
                "state": state.model_dump(mode="json"),
            },
        )
        self._event_bus.publish(mic_event)
