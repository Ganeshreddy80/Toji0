"""Strategy Engine Subsystem Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from strategy.core.events import (
    StrategyInitialized,
    StrategyShutdown,
)
from strategy.core.exceptions import StrategyException
from strategy.core.interfaces import (
    IStrategyEngine,
    IStrategyRegistry,
    IStrategyRepository,
    IStrategyStateStore,
)
from strategy.core.registry import StrategyRegistry
from strategy.core.repository import StrategyRepository
from strategy.core.state import StrategyStateStore
from strategy.analysis.strategy_engine import StrategyEngine
from strategy.core.orchestrator import StrategyOrchestrator
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from market_intelligence.core.interfaces import IStateStore
from price_action.core.interfaces import IPatternStateStore
from confluence.core.interfaces import IConfluenceStateStore
from toji_platform.strategy_engine.engine import StrategyEngine as NewStrategyEngine
from toji_platform.strategy_engine.adapter import LegacyStrategyAdapter
from strategy.analysis.trend_strategy import TrendFollowingStrategy

logger = logging.getLogger(__name__)


class StrategyPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Strategy Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IStrategyStateStore | None = None,
        repository: IStrategyRepository | None = None,
        strategy_engine: IStrategyEngine | None = None,
        orchestrator: StrategyOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._strategy_engine = strategy_engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("strategy")

    @property
    def name(self) -> str:
        return "Strategy Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        return [
            PluginId("market_intelligence"),
            PluginId("price_action"),
            PluginId("confluence"),
        ]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems and DI registrations."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Strategy Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise StrategyException(
                "Event Bus is required to initialize the Strategy plugin."
            )

        # 2. Setup state and repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get(
                "strategy.history_limit", 1000
            )

        if self._state_store is None:
            self._state_store = StrategyStateStore(history_limit=history_limit)

        if self._repository is None:
            storage_engine = None
            if self._container is not None:
                for key in [
                    "storage_engine",
                    "postgres_storage",
                    "data.storage.interfaces.IPostgresStorageEngine",
                ]:
                    if self._container.has(key):
                        try:
                            storage_engine = self._container.resolve(key)
                            break
                        except Exception:
                            pass
            self._repository = StrategyRepository(storage_engine=storage_engine)

        # 3. Setup StrategyEngine & Orchestrator
        if self._strategy_engine is None:
            self._strategy_engine = StrategyEngine(container=self._container)

        if self._orchestrator is None:
            self._orchestrator = StrategyOrchestrator()

        # Try resolving store dependencies for Orchestrator
        market_state_store = None
        pattern_state_store = None
        confluence_state_store = None

        if self._container is not None:
            if self._container.has(IStateStore):
                market_state_store = self._container.resolve(IStateStore)
            if self._container.has(IPatternStateStore):
                pattern_state_store = self._container.resolve(IPatternStateStore)
            if self._container.has(IConfluenceStateStore):
                confluence_state_store = self._container.resolve(IConfluenceStateStore)

        self._orchestrator.initialize(
            strategy_engine=self._strategy_engine,
            state_store=self._state_store,
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
            market_state_store=market_state_store,
            pattern_state_store=pattern_state_store,
            confluence_state_store=confluence_state_store,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(IStrategyStateStore):
                self._container.register(
                    IStrategyStateStore, instance=self._state_store
                )
            if not self._container.has(IStrategyRepository):
                self._container.register(
                    IStrategyRepository, instance=self._repository
                )
            if not self._container.has(IStrategyEngine):
                self._container.register(
                    IStrategyEngine, instance=self._strategy_engine
                )
            if hasattr(self._strategy_engine, "_selector") and hasattr(self._strategy_engine._selector, "registry"):
                if not self._container.has(IStrategyRegistry):
                    self._container.register(
                        IStrategyRegistry, instance=self._strategy_engine._selector.registry
                    )
            if not self._container.has(StrategyOrchestrator):
                self._container.register(
                    StrategyOrchestrator, instance=self._orchestrator
                )

        # 5. Subscribe to events
        self._subscribe_event(
            "system.market_state_updated", self._on_market_state_updated
        )
        self._subscribe_event(
            "system.pattern_updated", self._on_pattern_updated
        )
        self._subscribe_event(
            "system.pattern_quality_updated", self._on_pattern_quality_updated
        )
        self._subscribe_event(
            "system.confluence_updated", self._on_confluence_updated
        )
        self._subscribe_event(
            "system.confluence_completed", self._on_confluence_completed
        )

        # 6. Publish initialization event
        init_event = StrategyInitialized(
            source="strategy.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        # Initialize New Strategy Engine with LegacyStrategyAdapter in shadow mode
        try:
            self._new_strategy_engine = NewStrategyEngine(
                config=self._config_provider.get("strategies", {}) if self._config_provider else {}
            )
            legacy_trend = TrendFollowingStrategy()
            self._adapter = LegacyStrategyAdapter(
                name="LegacyTrendFollowing",
                legacy_strategy=legacy_trend,
                container=self._container
            )
            self._new_strategy_engine.register_strategy(self._adapter)
            logger.info("Initialized New Strategy Engine with LegacyStrategyAdapter wrapper in shadow mode ✓")
        except Exception as e:
            logger.error("Failed to initialize New Strategy Engine in shadow mode: %s", e)

        self._state = ModuleState.RUNNING
        logger.info("Strategy Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Strategy Engine plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error(
                        "Strategy: Failed to unsubscribe from %s: %s",
                        event_type,
                        e,
                    )
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = StrategyShutdown(
                    source="strategy.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error(
                    "Strategy: Failed to publish StrategyShutdown event: %s",
                    e,
                )

        # Shutdown New Strategy Engine
        if hasattr(self, "_new_strategy_engine") and self._new_strategy_engine:
            try:
                self._new_strategy_engine.unregister_strategy("LegacyTrendFollowing")
            except Exception as e:
                logger.error("Failed to unregister shadow strategy: %s", e)

        # 3. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("Strategy: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Strategy Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin status."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if (
            self._state_store is None
            or self._repository is None
            or self._orchestrator is None
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        """Connect callback handler in the event bus."""
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_market_state_updated(self, event: Any) -> None:
        """Process incoming analytical updates from the MIL."""
        logger.debug(
            "Strategy: Received MarketStateUpdated event from %s", event.source
        )
        self._process_event_state(event)

    def _on_pattern_updated(self, event: Any) -> None:
        """Process incoming pattern updates from PAE."""
        logger.debug(
            "Strategy: Received PatternUpdated event from %s", event.source
        )
        self._process_event_state(event)

    def _on_pattern_quality_updated(self, event: Any) -> None:
        """Process incoming pattern quality updates from PQE."""
        logger.debug(
            "Strategy: Received PatternQualityUpdated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _on_confluence_updated(self, event: Any) -> None:
        """Process incoming confluence updates from CE."""
        logger.debug(
            "Strategy: Received ConfluenceUpdated event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _on_confluence_completed(self, event: Any) -> None:
        """Process incoming confluence completed updates from CE."""
        logger.debug(
            "Strategy: Received ConfluenceCompleted event from %s",
            event.source,
        )
        self._process_event_state(event)

    def _process_event_state(self, event: Any) -> None:
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        symbol = event.payload.get("symbol")
        timeframe = event.payload.get("timeframe")

        if not (symbol and timeframe):
            # Try to fall back to nested state/pattern/quality fields
            for key in ("state", "pattern", "quality", "confluence", "candidate", "match"):
                nested = event.payload.get(key)
                if nested and isinstance(nested, dict):
                    symbol = symbol or nested.get("symbol")
                    timeframe = timeframe or nested.get("timeframe")

        if not (symbol and timeframe):
            return

        legacy_state = None
        try:
            if self._orchestrator is not None:
                legacy_state = self._orchestrator.process_strategy(symbol, timeframe)
        except Exception as e:
            logger.error(
                "Strategy: Failed to process event update for %s %s: %s",
                symbol,
                timeframe,
                e,
            )

        # Shadow execution and verification path
        if hasattr(self, "_new_strategy_engine") and self._new_strategy_engine:
            import time
            from datetime import datetime, timezone
            from toji_platform.market_scanner.models import MarketMetrics, MarketScan
            from strategy.core.enums import StrategyDecision

            # Query underlying stores to check legacy trend strategy inputs
            market_store = self._container.resolve(IStateStore) if self._container and self._container.has(IStateStore) else None
            market_snapshot = market_store.get_snapshot(symbol) if market_store else None
            market_state = market_snapshot.states.get(timeframe) if market_snapshot else None

            pattern_store = self._container.resolve(IPatternStateStore) if self._container and self._container.has(IPatternStateStore) else None
            pattern_snapshot = pattern_store.get_snapshot(symbol) if pattern_store else None
            pattern_state = pattern_snapshot.states.get(timeframe) if pattern_snapshot else None

            confluence_store = self._container.resolve(IConfluenceStateStore) if self._container and self._container.has(IConfluenceStateStore) else None
            confluence_snapshot = confluence_store.get_snapshot(symbol) if confluence_store else None
            confluence_state = confluence_snapshot.states.get(timeframe) if confluence_snapshot else None

            # Construct scan context
            metrics = MarketMetrics(
                atr=0.0,
                volatility=0.0,
                rsi=50.0,
                relative_volume=1.0,
                spread=0.0,
                liquidity_depth=10000.0,
                time_since_last_update_sec=0.0
            )
            scan = MarketScan(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc),
                market_states=[],
                metrics=metrics,
                confidence_score=1.0,
                quality_score=1.0,
                diagnostics={"timeframe": timeframe}
            )

            start_t = time.perf_counter()
            shadow_ideas = []
            shadow_duration = 0.0
            shadow_success = False
            shadow_error = None
            try:
                results = self._new_strategy_engine.execute_all([scan])
                shadow_duration = (time.perf_counter() - start_t) * 1000.0
                shadow_result = next((r for r in results if r.strategy_name == "LegacyTrendFollowing"), None)
                if shadow_result:
                    shadow_ideas = shadow_result.trade_ideas
                    shadow_success = shadow_result.success
                    shadow_error = shadow_result.error_message
            except Exception as ex:
                shadow_error = str(ex)

            # Evaluate expected legacy signal for specific TrendFollowing strategy to do direct parity comparison
            expected_signal = None
            if hasattr(self, "_adapter") and self._adapter:
                try:
                    expected_signal = self._adapter.legacy_strategy.evaluate(market_state, pattern_state, confluence_state)
                except Exception as ex_eval:
                    logger.error("Failed to evaluate trend strategy for verification: %s", ex_eval)

            # Compare outputs
            mismatch_field = None
            mismatch_reason = None
            is_pass = True

            diagnostics_used = {
                "market_state_found": market_state is not None,
                "pattern_state_found": pattern_state is not None,
                "confluence_state_found": confluence_state is not None,
                "shadow_success": shadow_success,
                "shadow_error": shadow_error
            }

            if expected_signal and expected_signal.decision != StrategyDecision.WAIT:
                if len(shadow_ideas) != 1:
                    is_pass = False
                    mismatch_field = "idea_count"
                    mismatch_reason = f"Expected 1 trade idea, got {len(shadow_ideas)}"
                else:
                    idea = shadow_ideas[0]
                    expected_dir = "LONG" if expected_signal.decision == StrategyDecision.BUY else "SHORT"
                    expected_conf = expected_signal.confidence
                    if expected_conf > 1.0:
                        expected_conf /= 100.0
                    expected_conf = round(expected_conf, 4)

                    if idea.symbol != symbol:
                        is_pass = False
                        mismatch_field = "symbol"
                        mismatch_reason = f"Expected symbol '{symbol}', got '{idea.symbol}'"
                    elif idea.direction != expected_dir:
                        is_pass = False
                        mismatch_field = "direction"
                        mismatch_reason = f"Expected direction '{expected_dir}', got '{idea.direction}'"
                    elif abs(idea.confidence - expected_conf) > 0.0001:
                        is_pass = False
                        mismatch_field = "confidence"
                        mismatch_reason = f"Expected confidence {expected_conf}, got {idea.confidence}"
                    elif idea.reason != expected_signal.reasoning:
                        is_pass = False
                        mismatch_field = "reason"
                        mismatch_reason = f"Expected reason '{expected_signal.reasoning}', got '{idea.reason}'"
            else:
                if len(shadow_ideas) != 0:
                    is_pass = False
                    mismatch_field = "idea_count"
                    mismatch_reason = f"Expected 0 trade ideas (WAIT posture), got {len(shadow_ideas)}: {shadow_ideas}"

            status_str = "PASS" if is_pass else "FAIL"
            logger.info(
                "SHADOW COMPARISON [%s] - Symbol: %s, Timeframe: %s | "
                "Legacy: %s, New (Shadow): %s | Duration: %.2fms | Diagnostics: %s",
                status_str, symbol, timeframe,
                expected_signal.decision.value if expected_signal else "None",
                shadow_ideas[0].direction if shadow_ideas else "FLAT/None",
                shadow_duration, diagnostics_used
            )
            if not is_pass:
                logger.error(
                    "SHADOW COMPARISON FAILURE - Field: '%s' | Reason: %s | Legacy: %s",
                    mismatch_field, mismatch_reason, expected_signal
                )

    @property
    def state_store(self) -> IStrategyStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IStrategyRepository | None:
        return self._repository

    @property
    def strategy_engine(self) -> IStrategyEngine | None:
        return self._strategy_engine

    @property
    def orchestrator(self) -> StrategyOrchestrator | None:
        return self._orchestrator
