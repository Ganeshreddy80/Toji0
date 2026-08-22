"""Confluence Orchestrator for managing pipeline execution and event dispatching."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.interfaces import IStateStore
from market_intelligence.core.models import MarketState
from price_action.core.interfaces import IPatternStateStore
from price_action.core.models import PatternState
from confluence.core.enums import SetupGrade
from confluence.core.events import (
    ConfluenceUpdated,
    SetupDetected,
    SetupRejected,
    SetupGradeChanged,
    ConfluenceScoreUpdated,
    TradeGradeUpdated,
    OpportunityUpdated,
)
from confluence.core.exceptions import OrchestratorError
from confluence.core.interfaces import (
    IConfluenceEngine,
    IConfluenceRepository,
    IConfluenceStateStore,
)
from confluence.core.models import (
    ConfluenceSnapshot,
    ConfluenceState,
)
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class ConfluenceOrchestrator:
    """Coordinates confluence evaluations, state storage, persistence, and event bus broadcasts."""

    def __init__(self) -> None:
        self._confluence_engine: IConfluenceEngine | None = None
        self._state_store: IConfluenceStateStore | None = None
        self._repository: IConfluenceRepository | None = None
        self._event_bus: IEventBus | None = None
        self._container: IContainer | None = None
        self._market_state_store: IStateStore | None = None
        self._pattern_state_store: IPatternStateStore | None = None

    def initialize(
        self,
        confluence_engine: IConfluenceEngine,
        state_store: IConfluenceStateStore,
        repository: IConfluenceRepository,
        event_bus: IEventBus | None = None,
        container: IContainer | None = None,
        market_state_store: IStateStore | None = None,
        pattern_state_store: IPatternStateStore | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._confluence_engine = confluence_engine
        self._state_store = state_store
        self._repository = repository
        self._event_bus = event_bus
        self._container = container
        self._market_state_store = market_state_store
        self._pattern_state_store = pattern_state_store

        # Resolve state stores from container if not directly provided
        if container is not None:
            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
            if self._market_state_store is None and container.has(IStateStore):
                self._market_state_store = container.resolve(IStateStore)
            if self._pattern_state_store is None and container.has(IPatternStateStore):
                self._pattern_state_store = container.resolve(IPatternStateStore)

    def process_confluence(self, symbol: str, timeframe: str) -> ConfluenceState:
        """Run confluence scoring pipeline for a given symbol and timeframe."""
        if not self._confluence_engine or not self._state_store or not self._repository:
            raise OrchestratorError("Orchestrator is not initialized.")

        if not self._market_state_store:
            raise OrchestratorError("Market state store is not resolved/provided.")

        try:
            # 1. Retrieve the latest MarketState
            market_snapshot = self._market_state_store.get_snapshot(symbol)
            market_state = (
                market_snapshot.states.get(timeframe)
                if market_snapshot
                else None
            )

            if not market_state:
                raise OrchestratorError(
                    f"No MarketState found for symbol '{symbol}' timeframe '{timeframe}'."
                )

            # 2. Retrieve the latest PatternState (optional)
            pattern_state = None
            if self._pattern_state_store:
                pattern_snapshot = self._pattern_state_store.get_snapshot(symbol)
                pattern_state = (
                    pattern_snapshot.states.get(timeframe)
                    if pattern_snapshot
                    else None
                )

            # 3. Retrieve previous state for comparison
            prev_snapshot = self._state_store.get_snapshot(symbol)
            prev_state = (
                prev_snapshot.states.get(timeframe) if prev_snapshot else None
            )

            # 4. Evaluate confluence score
            score = self._confluence_engine.evaluate(market_state, pattern_state)

            # 5. Build new ConfluenceState
            confluence_state = ConfluenceState(
                symbol=symbol,
                timeframe=timeframe,
                score=score,
                updated_at=datetime.now(timezone.utc),
            )

            # 6. Create snapshot if first timeframe update for symbol
            if prev_snapshot is None:
                prev_snapshot = ConfluenceSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=confluence_state.updated_at,
                    states={},
                )
                self._state_store.update_snapshot(prev_snapshot)

            # 7. Update the state store
            updated_snapshot = self._state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=confluence_state,
            )

            # 8. Persist to repository
            self._repository.save_snapshot(updated_snapshot)

            # 9. Dispatch events
            self._dispatch_events(prev_state, confluence_state)

            return confluence_state

        except Exception as e:
            logger.error("ConfluenceOrchestrator: Execution failed: %s", e)
            raise OrchestratorError(f"Failed to process confluence: {e}") from e

    def _dispatch_events(
        self, prev_state: ConfluenceState | None, curr_state: ConfluenceState
    ) -> None:
        """Analyze differences between states and publish transition events."""
        if self._event_bus is None:
            return

        symbol = curr_state.symbol
        timeframe = curr_state.timeframe
        source = "confluence.orchestrator"

        old_grade = prev_state.score.setup_grade if prev_state else None
        new_grade = curr_state.score.setup_grade

        state_json = curr_state.model_dump(mode="json")

        # 1. Always publish ConfluenceUpdated
        updated_event = ConfluenceUpdated(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "state": state_json,
            },
        )
        self._event_bus.publish(updated_event)

        # Publish ConfluenceCompleted event for downstream pipelines
        from toji_platform.core.event_bus.events import ConfluenceCompleted
        cc_event = ConfluenceCompleted(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "state": state_json,
            },
        )
        self._event_bus.publish(cc_event)

        # 2. Always publish ConfluenceScoreUpdated
        score_event = ConfluenceScoreUpdated(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "overall_score": curr_state.score.overall_score,
                "grade": new_grade.value,
            },
        )
        self._event_bus.publish(score_event)

        # 3. Publish OpportunityUpdated if opportunity data exists
        if curr_state.score.opportunity is not None:
            opp = curr_state.score.opportunity
            opp_event = OpportunityUpdated(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "opportunity_score": opp.opportunity_score,
                    "setup_quality": opp.setup_quality,
                    "execution_quality": opp.execution_quality,
                    "expected_rr": opp.expected_rr,
                },
            )
            self._event_bus.publish(opp_event)

        # 4. Check for Grade Transition
        if old_grade is not None and old_grade != new_grade:
            grade_changed_event = SetupGradeChanged(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "old_grade": old_grade.value,
                    "new_grade": new_grade.value,
                    "state": state_json,
                },
            )
            self._event_bus.publish(grade_changed_event)

            # Also publish TradeGradeUpdated
            tg_event = TradeGradeUpdated(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "old_grade": old_grade.value,
                    "new_grade": new_grade.value,
                },
            )
            self._event_bus.publish(tg_event)

        # 5. Check for high-grade setup detection
        high_grades = (SetupGrade.A_PLUS, SetupGrade.A, SetupGrade.B_PLUS, SetupGrade.B)
        if new_grade in high_grades and (
            old_grade is None or old_grade not in high_grades
        ):
            detected_event = SetupDetected(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "state": state_json,
                },
            )
            self._event_bus.publish(detected_event)

        # 6. Check for setup rejection (No Trade)
        if new_grade == SetupGrade.NO_TRADE and (
            old_grade is not None and old_grade != SetupGrade.NO_TRADE
        ):
            rejected_event = SetupRejected(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "state": state_json,
                },
            )
            self._event_bus.publish(rejected_event)
