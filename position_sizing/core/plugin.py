"""Position Sizing Subsystem Plugin implementation."""

from __future__ import annotations

import logging
from typing import Any

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from trading_context.core.models import TradingContext
from trading_context.core.interfaces import ITradingContextStateStore
from risk_engine.core.models import RiskState, RiskAssessment
from risk_engine.core.enums import RiskDecision
from position_sizing.core.events import (
    PositionSizingInitialized,
    PositionSizingShutdown,
)
from position_sizing.core.exceptions import PositionSizingError
from position_sizing.core.enums import SizingStatus
from position_sizing.core.models import PositionSizingResult
from position_sizing.core.interfaces import (
    IPositionSizingRepository,
    IPositionSizingStateStore,
    IPositionSizingEngine,
)
from position_sizing.core.repository import PositionSizingRepository
from position_sizing.core.state import PositionSizingStateStore
from position_sizing.analysis.position_engine import PositionSizingEngine
from position_sizing.core.orchestrator import PositionSizingOrchestrator

logger = logging.getLogger(__name__)


class PositionSizingPlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Position Sizing Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IPositionSizingStateStore | None = None,
        repository: IPositionSizingRepository | None = None,
        sizing_engine: IPositionSizingEngine | None = None,
        orchestrator: PositionSizingOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._sizing_engine = sizing_engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._active_subscriptions: list[tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("position_sizing")

    @property
    def name(self) -> str:
        return "Position Sizing Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> list[PluginId]:
        # Depends on Risk Engine which validates the Trading Context first
        return [PluginId("risk_engine"), PluginId("trading_context")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems, DI registrations, and event subscribers."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Position Sizing Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise PositionSizingError(
                "Event Bus is required to initialize the Position Sizing Engine plugin."
            )

        # 2. Setup state and repository
        history_limit = 1000
        if self._config_provider is not None:
            history_limit = self._config_provider.get(
                "sizing.history_limit", 1000
            )

        if self._state_store is None:
            self._state_store = PositionSizingStateStore(history_limit=history_limit)

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
            self._repository = PositionSizingRepository(storage_engine=storage_engine)

        # 3. Setup sizing engine and orchestrator
        if self._sizing_engine is None:
            self._sizing_engine = PositionSizingEngine()

        if self._orchestrator is None:
            self._orchestrator = PositionSizingOrchestrator()

        self._orchestrator.initialize(
            state_store=self._state_store,
            repository=self._repository,
            sizing_engine=self._sizing_engine,
            event_bus=self._event_bus,
            config_provider=self._config_provider,
            container=self._container,
        )

        # 4. Register services in DI container
        if self._container is not None:
            if not self._container.has(IPositionSizingStateStore):
                self._container.register(
                    IPositionSizingStateStore, instance=self._state_store
                )
            if not self._container.has(IPositionSizingRepository):
                self._container.register(
                    IPositionSizingRepository, instance=self._repository
                )
            if not self._container.has(IPositionSizingEngine):
                self._container.register(
                    IPositionSizingEngine, instance=self._sizing_engine
                )
            if not self._container.has(PositionSizingOrchestrator):
                self._container.register(
                    PositionSizingOrchestrator, instance=self._orchestrator
                )

        # 5. Subscribe to risk events
        self._subscribe_event(
            "system.risk_approved", self._on_risk_approved
        )
        self._subscribe_event(
            "system.risk_rejected", self._on_risk_rejected
        )
        self._subscribe_event(
            "system.risk_checked", self._on_risk_checked
        )

        # 6. Publish initialization event
        init_event = PositionSizingInitialized(
            source="position_sizing.plugin",
            payload={"version": self.version},
        )
        self._event_bus.publish(init_event)

        self._state = ModuleState.RUNNING
        logger.info("Position Sizing Engine plugin running successfully ✓")

    def shutdown(self) -> None:
        """Release plugin resources gracefully."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Position Sizing Engine plugin...")

        # 1. Unsubscribe event bus subscriptions
        if self._event_bus is not None:
            for event_type, handler in list(self._active_subscriptions):
                try:
                    self._event_bus.unsubscribe(event_type, handler)
                except Exception as e:
                    logger.error(
                        "PositionSizing: Failed to unsubscribe from %s: %s",
                        event_type,
                        e,
                    )
        self._active_subscriptions.clear()

        # 2. Publish shutdown event
        if self._event_bus is not None:
            try:
                shutdown_event = PositionSizingShutdown(
                    source="position_sizing.plugin",
                    payload={"version": self.version},
                )
                self._event_bus.publish(shutdown_event)
            except Exception as e:
                logger.error(
                    "PositionSizing: Failed to publish PositionSizingShutdown event: %s",
                    e,
                )

        # 3. Clear state store
        if self._state_store is not None:
            try:
                self._state_store.clear()
            except Exception as e:
                logger.error("PositionSizing: Error clearing state store: %s", e)

        self._state = ModuleState.STOPPED
        logger.info("Position Sizing Engine plugin stopped successfully ✓")

    def health_check(self) -> HealthStatus:
        """Return plugin health state."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if (
            self._state_store is None
            or self._repository is None
            or self._sizing_engine is None
            or self._orchestrator is None
        ):
            return HealthStatus.DEGRADED

        return HealthStatus.HEALTHY

    def _subscribe_event(self, event_type: str, handler: Any) -> None:
        """Connect callback handler in the event bus."""
        self._event_bus.subscribe(event_type, handler)
        self._active_subscriptions.append((event_type, handler))

    def _on_risk_approved(self, event: Any) -> PositionSizingResult | None:
        """Trigger sizing calculation when risk is approved."""
        logger.debug(
            "PositionSizing: Received RiskApproved event from %s", event.source
        )
        return self._process_risk_event(event, approved=True)

    def _on_risk_rejected(self, event: Any) -> PositionSizingResult | None:
        """Record a rejected size calculation when risk is rejected."""
        logger.debug(
            "PositionSizing: Received RiskRejected event from %s", event.source
        )
        return self._process_risk_event(event, approved=False)

    def _on_risk_checked(self, event: Any) -> PositionSizingResult | None:
        """Process incoming risk checked events."""
        logger.debug(
            "PositionSizing: Received RiskChecked event from %s", event.source
        )
        if not event or not hasattr(event, "payload") or not event.payload:
            return None
        decision = event.payload.get("decision")
        approved = (decision == "ALLOW")
        return self._process_risk_event(event, approved=approved)

    def _process_risk_event(self, event: Any, approved: bool) -> PositionSizingResult | None:
        if not event or not hasattr(event, "payload") or not event.payload:
            return None

        symbol = event.payload.get("symbol")
        timeframe = event.payload.get("timeframe")
        state_dict = event.payload.get("state")

        if not symbol or not timeframe or not state_dict:
            return None

        try:
            # Reconstruct RiskState
            risk_state = RiskState(**state_dict)
            risk_assessment = risk_state.assessment

            # Task 3: Short-circuit immediately if RiskDecision is BLOCK or not approved
            if risk_assessment.decision == RiskDecision.BLOCK or not approved:
                logger.warning(
                    "PositionSizingPlugin: Pipeline short-circuited for %s/%s due to BLOCK decision in RiskAssessment.",
                    symbol,
                    timeframe,
                )
                violations_str = [
                    v.message if hasattr(v, "message") else str(v)
                    for v in risk_assessment.violations
                ] if risk_assessment.violations else ["Risk check failed."]
                reasons_str = [
                    f"Risk assessment rejected the trade proposal: {v}"
                    for v in violations_str
                ]
                return PositionSizingResult(
                    success=False,
                    status=SizingStatus.REJECTED,
                    position_size=None,
                    reasons=reasons_str,
                    violations=violations_str,
                )

            # Resolve ITradingContextStateStore to find the original context
            context = None
            if self._container is not None and self._container.has(ITradingContextStateStore):
                tc_store = self._container.resolve(ITradingContextStateStore)
                snapshot = tc_store.get_snapshot(symbol)
                if snapshot and timeframe in snapshot.states:
                    context = snapshot.states[timeframe]

            if context is None:
                logger.warning(
                    "PositionSizing: No active TradingContext found for %s/%s to calculate sizing.",
                    symbol,
                    timeframe,
                )
                return None

            if self._orchestrator is not None:
                state = self._orchestrator.process_context(context, risk_assessment)
                if state:
                    return state.result
                return None

        except Exception as e:
            logger.error(
                "PositionSizing: Failed to process risk event: %s",
                e,
            )
            return None

    @property
    def state_store(self) -> IPositionSizingStateStore | None:
        return self._state_store

    @property
    def repository(self) -> IPositionSizingRepository | None:
        return self._repository

    @property
    def sizing_engine(self) -> IPositionSizingEngine | None:
        return self._sizing_engine

    @property
    def orchestrator(self) -> PositionSizingOrchestrator | None:
        return self._orchestrator
