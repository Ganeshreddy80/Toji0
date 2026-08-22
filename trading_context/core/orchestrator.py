"""Trading Context Orchestrator for managing pipeline aggregation and event dispatching."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.interfaces import IStateStore
from price_action.core.interfaces import IPatternStateStore
from confluence.core.interfaces import IConfluenceStateStore
from strategy.core.interfaces import IStrategyStateStore
from trading_context.core.exceptions import ValidationError, OrchestratorError
from trading_context.core.interfaces import (
    ITradingContextRepository,
    ITradingContextStateStore,
)
from trading_context.core.models import (
    TradingContext,
    TradingContextSnapshot,
    ContextMetadata,
)
from trading_context.core.validation import ContextValidator
from trading_context.core.events import (
    TradingContextCreated,
    TradingContextUpdated,
    TradingContextInvalid,
)
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class TradingContextOrchestrator:
    """Coordinates aggregating upstream state layers, running validation, and updating stores/repositories."""

    def __init__(self) -> None:
        self._state_store: ITradingContextStateStore | None = None
        self._repository: ITradingContextRepository | None = None
        self._event_bus: IEventBus | None = None
        self._container: IContainer | None = None
        self._market_state_store: IStateStore | None = None
        self._pattern_state_store: IPatternStateStore | None = None
        self._confluence_state_store: IConfluenceStateStore | None = None
        self._strategy_state_store: IStrategyStateStore | None = None
        self._staleness_threshold: float = 30.0

    def initialize(
        self,
        state_store: ITradingContextStateStore,
        repository: ITradingContextRepository,
        event_bus: IEventBus | None = None,
        container: IContainer | None = None,
        market_state_store: IStateStore | None = None,
        pattern_state_store: IPatternStateStore | None = None,
        confluence_state_store: IConfluenceStateStore | None = None,
        strategy_state_store: IStrategyStateStore | None = None,
        staleness_threshold_seconds: float = 30.0,
    ) -> None:
        """Inject dependencies into the orchestrator."""
        self._state_store = state_store
        self._repository = repository
        self._event_bus = event_bus
        self._container = container
        self._market_state_store = market_state_store
        self._pattern_state_store = pattern_state_store
        self._confluence_state_store = confluence_state_store
        self._strategy_state_store = strategy_state_store
        self._staleness_threshold = staleness_threshold_seconds

        # Resolve from Container if container is available
        if container is not None:
            if self._event_bus is None and container.has(IEventBus):
                self._event_bus = container.resolve(IEventBus)
            if self._market_state_store is None and container.has(IStateStore):
                self._market_state_store = container.resolve(IStateStore)
            if self._pattern_state_store is None and container.has(IPatternStateStore):
                self._pattern_state_store = container.resolve(IPatternStateStore)
            if self._confluence_state_store is None and container.has(IConfluenceStateStore):
                self._confluence_state_store = container.resolve(IConfluenceStateStore)
            if self._strategy_state_store is None and container.has(IStrategyStateStore):
                self._strategy_state_store = container.resolve(IStrategyStateStore)

    def process_context(self, symbol: str, timeframe: str) -> TradingContext | None:
        """Fetch upstream layers, validate context, persist snapshot, and dispatch events."""
        if not self._state_store or not self._repository:
            raise OrchestratorError("Orchestrator is not initialized.")

        if not self._market_state_store:
            raise OrchestratorError("Market state store is not resolved/provided.")

        try:
            # 1. Fetch MarketState
            market_snapshot = self._market_state_store.get_snapshot(symbol)
            market_state = (
                market_snapshot.states.get(timeframe)
                if market_snapshot
                else None
            )

            # 2. Fetch PatternState (optional)
            pattern_state = None
            if self._pattern_state_store:
                pattern_snapshot = self._pattern_state_store.get_snapshot(symbol)
                pattern_state = (
                    pattern_snapshot.states.get(timeframe)
                    if pattern_snapshot
                    else None
                )

            # 3. Fetch ConfluenceState (optional)
            confluence_state = None
            if self._confluence_state_store:
                confluence_snapshot = self._confluence_state_store.get_snapshot(symbol)
                confluence_state = (
                    confluence_snapshot.states.get(timeframe)
                    if confluence_snapshot
                    else None
                )

            # 4. Fetch StrategyState & StrategySignal (StrategyState contains latest_signal)
            strategy_state = None
            strategy_signal = None
            if self._strategy_state_store:
                strategy_snapshot = self._strategy_state_store.get_snapshot(symbol)
                strategy_state = (
                    strategy_snapshot.states.get(timeframe)
                    if strategy_snapshot
                    else None
                )
                if strategy_state:
                    strategy_signal = strategy_state.latest_signal

            # 5. Fetch previous context
            prev_snapshot = self._state_store.get_snapshot(symbol)
            prev_context = (
                prev_snapshot.states.get(timeframe) if prev_snapshot else None
            )

            # 6. Run Context Validation
            try:
                ContextValidator.validate_states(
                    symbol=symbol,
                    timeframe=timeframe,
                    market_state=market_state,
                    pattern_state=pattern_state,
                    confluence_state=confluence_state,
                    strategy_state=strategy_state,
                    staleness_threshold_seconds=self._staleness_threshold,
                )
            except ValidationError as ve:
                logger.warning("Trading Context Validation failed: %s", ve)
                self._dispatch_invalid_event(symbol, timeframe, str(ve))
                return None

            # 7. Construct TradingContext
            metadata = ContextMetadata(
                engine_versions={
                    "market_intelligence": "1.0.0",
                    "price_action": "1.0.0",
                    "confluence": "1.0.0",
                    "strategy": "1.0.0",
                    "trading_context": "1.0.0",
                },
                replay_hash="",
                pipeline_version="1.0.0",
                source_events=["system.market_state_updated", "system.strategy_updated"],
                creation_timestamp=datetime.now(timezone.utc),
            )

            trading_context = TradingContext(
                symbol=symbol,
                timeframe=timeframe,
                market_state=market_state,
                pattern_state=pattern_state,
                confluence_state=confluence_state,
                strategy_state=strategy_state,
                strategy_signal=strategy_signal,
                metadata=metadata,
                generated_at=datetime.now(timezone.utc),
                replay_id=str(uuid.uuid4()),
                version="1.0.0",
            )

            # 8. Store in state store
            if prev_snapshot is None:
                prev_snapshot = TradingContextSnapshot(
                    snapshot_id=str(uuid.uuid4()),
                    symbol=symbol,
                    timestamp=trading_context.generated_at,
                    states={},
                )
                self._state_store.update_snapshot(prev_snapshot)

            updated_snapshot = self._state_store.update_timeframe_state(
                symbol=symbol,
                timeframe=timeframe,
                state_update=trading_context,
            )

            # 9. Persist to repository
            self._repository.save_snapshot(updated_snapshot)

            # 10. Dispatch Events
            self._dispatch_success_events(prev_context, trading_context)

            return trading_context

        except Exception as e:
            logger.error("TradingContextOrchestrator: Execution failed: %s", e)
            raise OrchestratorError(f"Failed to process trading context: {e}") from e

    def _dispatch_success_events(
        self, prev_context: TradingContext | None, curr_context: TradingContext
    ) -> None:
        """Publish created or updated context events to the event bus."""
        if self._event_bus is None:
            return

        symbol = curr_context.symbol
        timeframe = curr_context.timeframe
        source = "trading_context.orchestrator"
        context_json = curr_context.model_dump(mode="json")

        if prev_context is None:
            created_event = TradingContextCreated(
                source=source,
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "context": context_json,
                },
            )
            self._event_bus.publish(created_event)

        updated_event = TradingContextUpdated(
            source=source,
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "context": context_json,
            },
        )
        self._event_bus.publish(updated_event)

    def _dispatch_invalid_event(self, symbol: str, timeframe: str, reason: str) -> None:
        """Publish invalid context event to the event bus."""
        if self._event_bus is None:
            return

        invalid_event = TradingContextInvalid(
            source="trading_context.orchestrator",
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "reason": reason,
            },
        )
        self._event_bus.publish(invalid_event)
