"""Portfolio Construction Plugin managing lifecycle and event bus integration."""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

from portfolio_construction.core.interfaces import (
    IPortfolioConstructionEngine,
    IPortfolioConstructionRepository,
    IPortfolioConstructionStateStore,
)
from portfolio_construction.core.state import PortfolioConstructionStateStore
from portfolio_construction.core.repository import PortfolioConstructionRepository
from portfolio_construction.analysis.construction_engine import PortfolioConstructionEngine
from portfolio_construction.core.orchestrator import PortfolioConstructionOrchestrator
from portfolio_construction.core.exceptions import PortfolioConstructionException
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from strategy.core.models import StrategySignal

logger = logging.getLogger(__name__)


class PortfolioConstructionPlugin(IPlugin):
    """Lifecycle controller and dependency binder for the Portfolio Construction Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IPortfolioConstructionStateStore | None = None,
        repository: IPortfolioConstructionRepository | None = None,
        engine: IPortfolioConstructionEngine | None = None,
        orchestrator: PortfolioConstructionOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._engine = engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: List[Tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("portfolio_construction")

    @property
    def name(self) -> str:
        return "Portfolio Construction Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[PluginId]:
        return [PluginId("strategy")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems and DI registrations."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Portfolio Construction Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise PortfolioConstructionException("Event Bus is required to initialize Portfolio Construction plugin.")

        # 2. Setup state and repository
        if self._state_store is None:
            self._state_store = PortfolioConstructionStateStore()

        if self._repository is None:
            storage_engine = None
            if self._container is not None and self._container.has("storage_engine"):
                storage_engine = self._container.resolve("storage_engine")
            self._repository = PortfolioConstructionRepository(storage_engine=storage_engine)

        # 3. Setup Engine and Orchestrator
        if self._engine is None:
            self._engine = PortfolioConstructionEngine()

        if self._orchestrator is None:
            self._orchestrator = PortfolioConstructionOrchestrator()

        self._orchestrator.initialize(
            engine=self._engine,
            state_store=self._state_store,
            repository=self._repository,
            event_bus=self._event_bus,
            container=self._container,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(IPortfolioConstructionStateStore):
                self._container.register(IPortfolioConstructionStateStore, instance=self._state_store)
            if not self._container.has(IPortfolioConstructionRepository):
                self._container.register(IPortfolioConstructionRepository, instance=self._repository)
            if not self._container.has(IPortfolioConstructionEngine):
                self._container.register(IPortfolioConstructionEngine, instance=self._engine)
            if not self._container.has(PortfolioConstructionOrchestrator):
                self._container.register(PortfolioConstructionOrchestrator, instance=self._orchestrator)

        # 5. Subscribe to events
        self._subscribe_event("system.strategy_signal", self._on_strategy_signal)
        self._subscribe_event("system.strategy_generated", self._on_strategy_generated)

        self._state = ModuleState.RUNNING
        logger.info("Portfolio Construction Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Portfolio Construction Engine plugin...")

        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error("PortfolioConstruction: Failed to unsubscribe from %s: %s", event_type, e)
        self._active_subscriptions.clear()

        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("PortfolioConstruction: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Portfolio Construction Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if self._state_store is None or self._repository is None or self._orchestrator is None:
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_strategy_signal(self, event: Any) -> None:
        """Process incoming StrategySignalEvent from Strategy Engine."""
        logger.debug("PortfolioConstruction: Received StrategySignalEvent from %s", getattr(event, "source", "unknown"))
        self._process_signal_event(event)

    def _on_strategy_generated(self, event: Any) -> None:
        """Process incoming StrategyGenerated event from Strategy Engine."""
        logger.debug("PortfolioConstruction: Received StrategyGenerated event from %s", getattr(event, "source", "unknown"))
        self._process_signal_event(event)

    def _process_signal_event(self, event: Any) -> None:
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        try:
            signal_data = event.payload.get("signal") or event.payload.get("latest_signal")
            if not signal_data or not isinstance(signal_data, dict):
                return

            # Reconstruct StrategySignal if valid dictionary
            from price_action.core.enums import PatternDirection
            from strategy.core.enums import StrategyDecision, StrategyType

            signal = StrategySignal(
                signal_id=signal_data.get("signal_id", "sig-default"),
                symbol=signal_data.get("symbol", "UNKNOWN"),
                timeframe=signal_data.get("timeframe", "1h"),
                direction=PatternDirection(signal_data.get("direction", "BULLISH")),
                strategy_type=StrategyType(signal_data.get("strategy_type", "Trend Following")),
                decision=StrategyDecision(signal_data.get("decision", "WAIT")),
                confidence=signal_data.get("confidence", 0.0),
                confluence_score=signal_data.get("confluence_score", 0.0),
                reasoning=signal_data.get("reasoning", "Event payload signal"),
            )

            if self._orchestrator is not None and signal.decision != StrategyDecision.WAIT:
                self._orchestrator.process_signals([signal])

        except Exception as e:
            logger.error("PortfolioConstruction: Failed to process strategy signal event: %s", e)

    @property
    def state_store(self) -> IPortfolioConstructionStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IPortfolioConstructionRepository | None:
        return self._repository

    @property
    def orchestrator(self) -> PortfolioConstructionOrchestrator | None:
        return self._orchestrator
