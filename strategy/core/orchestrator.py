"""Strategy Orchestrator for managing pipeline execution and event dispatching."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.interfaces import IStateStore
from market_intelligence.core.models import MarketState
from price_action.core.interfaces import IPatternStateStore
from price_action.core.models import PatternState
from confluence.core.interfaces import IConfluenceStateStore
from confluence.core.models import ConfluenceState
from strategy.core.enums import StrategyDecision, StrategyType
from strategy.core.events import (
    StrategyUpdated,
    StrategySignalEvent,
    StrategyChanged,
    StrategyRejected,
)
from strategy.core.exceptions import OrchestratorError
from strategy.core.interfaces import (
    IStrategyEngine,
    IStrategyRepository,
    IStrategyStateStore,
)
from strategy.core.models import (
    StrategySignal,
    StrategySnapshot,
    StrategyState,
)
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class StrategyOrchestrator:
    """Coordinates strategy evaluation, state storage, persistence, and event bus broadcasts."""

    def __init__(self) -> None:
        self._strategy_engine: IStrategyEngine | None = None
        self._state_store: IStrategyStateStore | None = None
        self._repository: IStrategyRepository | None = None
        self._event_bus: IEventBus | None = None
        self._container: IContainer | None = None
        self._market_state_store: IStateStore | None = None
        self._pattern_state_store: IPatternStateStore | None = None
        self._confluence_state_store: IConfluenceStateStore | None = None

    def initialize(
        self,
        strategy_engine: IStrategyEngine,
        state_store: IStrategyStateStore,
        repository: IStrategyRepository,
        event_bus: IEventBus | None = None,
        container: IContainer | None = None,
        market_state_store: IStateStore | None = None,
        pattern_state_store: IPatternStateStore | None = None,
        confluence_state_store: IConfluenceStateStore | None = None,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._strategy_engine = strategy_engine
        self._state_store = state_store
        self._repository = repository
        self._event_bus = event_bus
        self._container = container
        self._market_state_store = market_state_store
        self._pattern_state_store = pattern_state_store
        self._confluence_state_store = confluence_state_store

        # Resolve dependencies from Container if available
        if container is not None:
            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
            if self._market_state_store is None and container.has(IStateStore):
                self._market_state_store = container.resolve(IStateStore)
            if self._pattern_state_store is None and container.has(IPatternStateStore):
                self._pattern_state_store = container.resolve(IPatternStateStore)
            if self._confluence_state_store is None and container.has(IConfluenceStateStore):
                self._confluence_state_store = container.resolve(IConfluenceStateStore)

    def process_strategy(self, symbol: str, timeframe: str) -> StrategyState:
        """Run strategy scoring pipeline for a given symbol and timeframe."""
        if not self._strategy_engine or not self._state_store or not self._repository:
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
                logger.error("StrategyOrchestrator: No MarketState found for symbol '%s' timeframe '%s'. Failing closed to WAIT posture.", symbol, timeframe)
                from price_action.core.enums import PatternDirection
                fail_signal = StrategySignal(
                    signal_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timeframe=timeframe,
                    direction=PatternDirection.BULLISH,
                    strategy_type=StrategyType.TREND_FOLLOWING,
                    decision=StrategyDecision.WAIT,
                    confidence=0.0,
                    confluence_score=0.0,
                    reasoning=f"Fail-Closed: No MarketState available for symbol '{symbol}' timeframe '{timeframe}'.",
                    supporting_factors=[],
                    conflicting_factors=["Missing MarketState"],
                    detected_at=datetime.now(timezone.utc),
                )
                prev_snapshot = self._state_store.get_snapshot(symbol)
                prev_state = prev_snapshot.states.get(timeframe) if prev_snapshot else None
                historical = list(prev_state.historical_strategies) if prev_state else []
                fail_state = StrategyState(
                    symbol=symbol,
                    timeframe=timeframe,
                    active_strategy=None,
                    latest_signal=fail_signal,
                    historical_strategies=historical,
                    updated_at=datetime.now(timezone.utc),
                )
                if prev_snapshot is None:
                    prev_snapshot = StrategySnapshot(
                        snapshot_id=str(uuid.uuid4()),
                        symbol=symbol,
                        timestamp=fail_state.updated_at,
                        states={},
                    )
                    self._state_store.update_snapshot(prev_snapshot)
                updated_snap = self._state_store.update_timeframe_state(symbol, timeframe, fail_state)
                self._repository.save_snapshot(updated_snap)
                self._dispatch_events(prev_state, fail_state)
                return fail_state

            # 2. Retrieve the latest PatternState (optional)
            pattern_state = None
            if self._pattern_state_store:
                pattern_snapshot = self._pattern_state_store.get_snapshot(symbol)
                pattern_state = (
                    pattern_snapshot.states.get(timeframe)
                    if pattern_snapshot
                    else None
                )

            # 3. Retrieve the latest ConfluenceState (optional)
            confluence_state = None
            if self._confluence_state_store:
                confluence_snapshot = self._confluence_state_store.get_snapshot(symbol)
                confluence_state = (
                    confluence_snapshot.states.get(timeframe)
                    if confluence_snapshot
                    else None
                )

            # 4. Retrieve previous state for comparison
            prev_snapshot = self._state_store.get_snapshot(symbol)
            prev_state = (
                prev_snapshot.states.get(timeframe) if prev_snapshot else None
            )

            # 5. Evaluate strategy logic
            signal = self._strategy_engine.evaluate(
                market_state, pattern_state, confluence_state
            )

            # 6. Apply Signal Lifecycle States & Duplicate Signal Suppression
            from strategy.core.enums import SignalLifecycleState
            prev_sig = prev_state.latest_signal if prev_state else None

            if signal.decision != StrategyDecision.WAIT:
                if prev_sig and prev_sig.decision != StrategyDecision.WAIT and prev_sig.decision == signal.decision and prev_sig.strategy_type == signal.strategy_type and prev_sig.direction == signal.direction:
                    conf_delta = abs(signal.confidence - prev_sig.confidence)
                    if conf_delta < 0.02:
                        # Identical signal — mark as ACTIVE and suppress duplicate event broadcast
                        signal = signal.model_copy(update={"lifecycle_state": SignalLifecycleState.ACTIVE})
                    else:
                        # Material change in signal metrics — mark as UPDATED
                        signal = signal.model_copy(update={"lifecycle_state": SignalLifecycleState.UPDATED})
                else:
                    # Brand new signal trigger — mark as NEW
                    signal = signal.model_copy(update={"lifecycle_state": SignalLifecycleState.NEW})
            else:
                if prev_sig and prev_sig.decision != StrategyDecision.WAIT:
                    # Active signal expired back to WAIT
                    signal = signal.model_copy(update={"lifecycle_state": SignalLifecycleState.EXPIRED})

            # 7. Update strategy history and active state
            active_strategy = (
                signal.strategy_type
                if signal.decision != StrategyDecision.WAIT
                else None
            )

            historical = list(prev_state.historical_strategies) if prev_state else []
            if signal.decision != StrategyDecision.WAIT:
                # Avoid consecutive identical signals in history
                if (
                    not prev_state
                    or not prev_sig
                    or prev_sig.decision != signal.decision
                    or prev_sig.strategy_type != signal.strategy_type
                ):
                    historical.append(signal)

            strategy_state = StrategyState(
                symbol=symbol,
                timeframe=timeframe,
                active_strategy=active_strategy,
                latest_signal=signal,
                historical_strategies=historical,
                updated_at=datetime.now(timezone.utc),
            )

            # 8. Create snapshot if first timeframe update for symbol
            if prev_snapshot is None:
                prev_snapshot = StrategySnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=strategy_state.updated_at,
                    states={},
                )
                self._state_store.update_snapshot(prev_snapshot)

            # 9. Update the state store
            updated_snapshot = self._state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=strategy_state,
            )

            # 10. Persist to repository
            self._repository.save_snapshot(updated_snapshot)

            # 11. Dispatch events
            self._dispatch_events(prev_state, strategy_state)

            return strategy_state

        except Exception as e:
            logger.error(
                "StrategyOrchestrator: Runtime evaluation failed for '%s' '%s': %s. Failing closed to WAIT posture.",
                symbol,
                timeframe,
                e,
                exc_info=True,
            )
            from price_action.core.enums import PatternDirection
            fail_signal = StrategySignal(
                signal_id=str(uuid.uuid4()),
                symbol=symbol,
                timeframe=timeframe,
                direction=PatternDirection.BULLISH,
                strategy_type=StrategyType.TREND_FOLLOWING,
                decision=StrategyDecision.WAIT,
                confidence=0.0,
                confluence_score=0.0,
                reasoning=f"Fail-Closed: Strategy evaluation exception: {e}",
                supporting_factors=[],
                conflicting_factors=["Strategy Evaluation Error"],
                detected_at=datetime.now(timezone.utc),
            )
            try:
                prev_snapshot = self._state_store.get_snapshot(symbol)
                prev_state = prev_snapshot.states.get(timeframe) if prev_snapshot else None
                historical = list(prev_state.historical_strategies) if prev_state else []
                fail_state = StrategyState(
                    symbol=symbol,
                    timeframe=timeframe,
                    active_strategy=None,
                    latest_signal=fail_signal,
                    historical_strategies=historical,
                    updated_at=datetime.now(timezone.utc),
                )
                if prev_snapshot is None:
                    prev_snapshot = StrategySnapshot(
                        snapshot_id=str(uuid.uuid4()),
                        symbol=symbol,
                        timestamp=fail_state.updated_at,
                        states={},
                    )
                    self._state_store.update_snapshot(prev_snapshot)
                updated_snap = self._state_store.update_timeframe_state(symbol, timeframe, fail_state)
                self._repository.save_snapshot(updated_snap)
                self._dispatch_events(prev_state, fail_state)
                return fail_state
            except Exception as store_err:
                logger.error("StrategyOrchestrator: Failed to persist fail-closed state: %s", store_err)
                return StrategyState(
                    symbol=symbol,
                    timeframe=timeframe,
                    active_strategy=None,
                    latest_signal=fail_signal,
                    historical_strategies=[],
                    updated_at=datetime.now(timezone.utc),
                )

    def _dispatch_events(
        self, prev_state: StrategyState | None, curr_state: StrategyState
    ) -> None:
        """Analyze differences between states and publish transition events."""
        if self._event_bus is None:
            return

        symbol = curr_state.symbol
        timeframe = curr_state.timeframe
        source = "strategy.orchestrator"

        state_json = curr_state.model_dump(mode="json")
        signal = curr_state.latest_signal

        # 1. Always publish StrategyUpdated
        updated_event = StrategyUpdated(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "state": state_json,
            },
        )
        self._event_bus.publish(updated_event)

        # Publish StrategyGenerated event for downstream pipelines
        from toji_platform.core.event_bus.events import StrategyGenerated
        sg_event = StrategyGenerated(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "state": state_json,
                "latest_signal": signal.model_dump(mode="json") if signal else None,
            },
        )
        self._event_bus.publish(sg_event)

        # 2. Check for active signal trigger (Publish only for NEW or UPDATED signals, suppress ACTIVE duplicates)
        from strategy.core.enums import SignalLifecycleState
        signal = curr_state.latest_signal
        if signal and signal.decision != StrategyDecision.WAIT:
            if signal.lifecycle_state in (SignalLifecycleState.NEW, SignalLifecycleState.UPDATED):
                signal_event = StrategySignalEvent(
                    source=source,
                    payload={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "signal": signal.model_dump(mode="json"),
                    },
                )
                self._event_bus.publish(signal_event)

        # 3. Check for strategy transitions
        old_strat = prev_state.active_strategy if prev_state else None
        new_strat = curr_state.active_strategy
        if old_strat != new_strat and (old_strat is not None or new_strat is not None):
            changed_event = StrategyChanged(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "old_strategy": old_strat.value if old_strat else None,
                    "new_strategy": new_strat.value if new_strat else None,
                    "state": state_json,
                },
            )
            self._event_bus.publish(changed_event)

        # 4. Check for strategy rejection
        if old_strat is not None and new_strat is None:
            rejected_event = StrategyRejected(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "state": state_json,
                },
            )
            self._event_bus.publish(rejected_event)
