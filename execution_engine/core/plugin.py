from __future__ import annotations

import logging
from typing import Any, List, Tuple

from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPlugin
from toji_platform.core.types import HealthStatus, ModuleState, PluginId

from execution_engine.brokers.broker_router import BrokerRouter
from execution_engine.brokers.connection_manager import ConnectionManager
from execution_engine.brokers.paper_broker import PaperBroker
from execution_engine.brokers.binance_broker import BinanceBroker
from execution_engine.core.exceptions import ExecutionEngineError
from execution_engine.core.interfaces import (
    IExecutionEngine,
    IExecutionRepository,
    IExecutionStateStore,
)
from execution_engine.core.models import ExecutionConfig
from execution_engine.core.orchestrator import ExecutionOrchestrator
from execution_engine.core.repository import ExecutionRepository
from execution_engine.core.state import ExecutionStateStore
from execution_engine.core.validator import ExecutionDeduplicator, ExecutionValidator
from execution_engine.analysis.execution_engine import ExecutionEngine

logger = logging.getLogger(__name__)


class ExecutionEnginePlugin(IPlugin):
    """Lifecycle controller and dependency injection binder for the Execution Engine."""

    def __init__(
        self,
        event_bus: IEventBus | None = None,
        config_provider: IConfigProvider | None = None,
        container: IContainer | None = None,
        state_store: IExecutionStateStore | None = None,
        repository: IExecutionRepository | None = None,
        execution_engine: IExecutionEngine | None = None,
        orchestrator: ExecutionOrchestrator | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_provider = config_provider
        self._container = container
        self._state_store = state_store
        self._repository = repository
        self._execution_engine = execution_engine
        self._orchestrator = orchestrator

        self._state = ModuleState.CREATED
        self._broker_router: BrokerRouter | None = None
        self._connection_manager: ConnectionManager | None = None
        self._active_subscriptions: List[Tuple[str, Any]] = []

    @property
    def plugin_id(self) -> PluginId:
        return PluginId("execution_engine")

    @property
    def name(self) -> str:
        return "Execution Engine"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def dependencies(self) -> List[PluginId]:
        # Execution Engine runs after the Position Sizing Engine
        return [PluginId("position_sizing"), PluginId("risk_engine")]

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        """Initialize all subsystems, DI registrations, and event subscribers."""
        if self._state == ModuleState.RUNNING:
            return

        self._state = ModuleState.INITIALIZING
        logger.info("Initializing Execution Engine plugin...")

        # 1. Resolve container dependencies
        if self._container is not None:
            if self._event_bus is None and self._container.has(IEventBus):
                self._event_bus = self._container.resolve(IEventBus)
            if self._config_provider is None and self._container.has(IConfigProvider):
                self._config_provider = self._container.resolve(IConfigProvider)

        if self._event_bus is None:
            self._state = ModuleState.FAILED
            raise ExecutionEngineError("Event Bus is required to initialize the Execution Engine plugin.")

        # 2. Compile Config options from ConfigProvider
        config_params = {}
        if self._config_provider:
            config_params["broker_selection"] = self._config_provider.get("execution.broker", "paper")
            config_params["timeouts_ms"] = self._config_provider.get("execution.timeouts", {"submit": 5000})
            config_params["retry_policy"] = self._config_provider.get("execution.retry_policy", {"max_retries": 3, "initial_delay_seconds": 0.2})
            config_params["min_notional_rules"] = self._config_provider.get("execution.min_notional", {"BTC": 0.001, "BTC_NOTIONAL": 10.0})
            config_params["tick_size_rules"] = self._config_provider.get("execution.tick_size", {"BTC": 0.01})
            config_params["precision_rules"] = self._config_provider.get("execution.precision", {"BTC": {"quantity": 4}})
            config_params["paper_broker_settings"] = self._config_provider.get(
                "execution.paper_settings",
                {
                    "initial_balance": 100000.0,
                    "commission_rate": 0.001,
                    "slippage_rate": 0.0005,
                    "enable_partial_fills": False,
                },
            )

        execution_config = ExecutionConfig(**config_params)

        # 3. Instantiate core components if not explicitly injected
        if self._state_store is None:
            self._state_store = ExecutionStateStore()
        if self._repository is None:
            self._repository = ExecutionRepository()

        # 4. Set up Broker Router & Adapters
        self._broker_router = BrokerRouter()
        paper_settings = execution_config.paper_broker_settings
        paper_adapter = PaperBroker(paper_settings)
        binance_adapter = BinanceBroker({})

        self._broker_router.register_adapter("paper", paper_adapter)
        self._broker_router.register_adapter("binance", binance_adapter)

        # Connect active broker
        active_broker_name = execution_config.broker_selection
        active_broker = self._broker_router.get_adapter(active_broker_name)
        
        # Connection monitoring
        self._connection_manager = ConnectionManager(
            active_broker,
            heartbeat_interval_sec=execution_config.heartbeat_interval_seconds,
            reconnect_interval_sec=execution_config.reconnect_interval_seconds,
        )
        self._connection_manager.start()

        # 5. Set up Validator & Deduplicator
        deduplicator = ExecutionDeduplicator()
        validator = ExecutionValidator(execution_config, deduplicator)

        # Instantiate new OMS and Analytics layers
        from execution_engine.analysis.analytics import ExecutionAnalyticsCalculator
        self._analytics_calculator = ExecutionAnalyticsCalculator()

        # 6. Instantiate Execution Engine
        if self._execution_engine is None:
            self._execution_engine = ExecutionEngine(
                config=execution_config,
                broker_router=self._broker_router,
                validator=validator,
                repository=self._repository,
                state_store=self._state_store,
                analytics=self._analytics_calculator,
            )

        from execution_engine.core.oms import OrderManager, FillManager, BrokerManager, ExecutionManager
        from execution_engine.analysis.replay import ExecutionReplayEngine
        self._order_manager = OrderManager()
        self._fill_manager = FillManager()
        self._broker_manager = BrokerManager()
        
        # Register adapters in BrokerManager
        self._broker_manager.register_broker("paper", paper_adapter)
        self._broker_manager.register_broker("binance", binance_adapter)
        
        self._execution_manager = ExecutionManager(
            self._order_manager, self._fill_manager, self._broker_manager
        )
        self._replay_engine = ExecutionReplayEngine(self._execution_engine)

        from execution_engine.oms.recovery import RecoveryManager
        self._recovery_manager = RecoveryManager(
            broker_router=self._broker_router,
            event_bus=self._event_bus,
            execution_repository=self._repository,
        )

        # 7. Setup Orchestrator
        if self._orchestrator is None:
            self._orchestrator = ExecutionOrchestrator()
            self._orchestrator.initialize(
                state_store=self._state_store,
                repository=self._repository,
                execution_engine=self._execution_engine,
                event_bus=self._event_bus,
                config_provider=self._config_provider,
                container=self._container,
            )

        # 8. DI registrations
        if self._container is not None:
            from execution_engine.oms.oms_core import OmsCore
            from execution_engine.ems.ems_engine import EmsEngine
            from execution_engine.core.interfaces import IOmsCore, IEmsEngine

            self._container.register(IExecutionStateStore, self._state_store)
            self._container.register(IExecutionRepository, self._repository)
            self._container.register(IExecutionEngine, self._execution_engine)
            self._container.register(OrderManager, self._order_manager)
            self._container.register(FillManager, self._fill_manager)
            self._container.register(BrokerManager, self._broker_manager)
            self._container.register(ExecutionManager, self._execution_manager)
            self._container.register(ExecutionAnalyticsCalculator, self._analytics_calculator)
            self._container.register(ExecutionReplayEngine, self._replay_engine)
            
            # Sprint 8 DI registrations
            self._container.register(IOmsCore, self._execution_engine.oms)
            self._container.register(IEmsEngine, self._execution_engine.ems)
            self._container.register(OmsCore, self._execution_engine.oms)
            self._container.register(EmsEngine, self._execution_engine.ems)
            self._container.register(RecoveryManager, self._recovery_manager)

        # 9. Subscribe to upstream Events
        subscription_id = self._event_bus.subscribe(
            "system.position_size_calculated",
            self._orchestrator.on_position_size_calculated,
        )
        self._active_subscriptions.append(("system.position_size_calculated", subscription_id))

        sub_approved_id = self._event_bus.subscribe(
            "system.execution_approved",
            self._orchestrator.on_execution_approved,
        )
        self._active_subscriptions.append(("system.execution_approved", sub_approved_id))

        self._state = ModuleState.RUNNING
        logger.info("Execution Engine subsystem initialization complete.")

    def shutdown(self) -> None:
        """Gracefully unsubscribe and shutdown connections."""
        if self._state in (ModuleState.STOPPED, ModuleState.CREATED):
            return

        self._state = ModuleState.STOPPING
        logger.info("Shutting down Execution Engine plugin...")

        # Unsubscribe events
        if self._event_bus:
            for topic, sub_id in self._active_subscriptions:
                try:
                    self._event_bus.unsubscribe(topic, sub_id)
                except Exception as e:
                    logger.error("Failed to unsubscribe topic %s: %s", topic, e)
            self._active_subscriptions.clear()

        # Stop connection manager
        if self._connection_manager:
            try:
                self._connection_manager.stop()
            except Exception as e:
                logger.error("Failed to stop ConnectionManager: %s", e)
            self._connection_manager = None

        self._state = ModuleState.STOPPED
        logger.info("Execution Engine shutdown complete.")

    def health_check(self) -> HealthStatus:
        """Get the combined health status of the plugin and the broker connection."""
        if self._state != ModuleState.RUNNING:
            return HealthStatus.UNHEALTHY

        if self._connection_manager:
            conn_status = self._connection_manager.connectivity
            if conn_status == "CONNECTED":
                return HealthStatus.HEALTHY
            elif conn_status == "RECONNECTING":
                return HealthStatus.DEGRADED

        return HealthStatus.UNHEALTHY
