"""TOJI Platform Startup Coordinator.
"""

from __future__ import annotations

import logging
from typing import Any, List

from research_platform.platform.configuration_boot import ConfigurationBootloader
from research_platform.platform.database_boot import DatabaseLifecycleManager
from research_platform.platform.container_boot import ContainerBootloader
from research_platform.platform.eventbus_boot import EventBusBootloader
from research_platform.platform.plugin_loader import PluginLoader
from research_platform.platform.service_registry import ServiceRegistry

logger = logging.getLogger(__name__)


class PlatformStartupCoordinator:
    """Orchestrates configuration loading, database connection, plugin discovery, and boot sequencing."""

    def __init__(self) -> None:
        self.config_loader = ConfigurationBootloader()
        self.container_boot = ContainerBootloader()
        self.eventbus_boot = EventBusBootloader()
        self.plugin_loader = PluginLoader()
        self.service_registry = ServiceRegistry()

    def boot_platform(self) -> None:
        logger.info("Initializing TOJI V1 Platform Boot Sequence...")

        # 1. Configuration
        config = self.config_loader.load_configuration()
        self.service_registry.register_service("Configuration", config)

        # 2. Database
        db_manager = DatabaseLifecycleManager(config["database"])
        db_manager.connect()
        self.service_registry.register_service("Database", db_manager)

        # 3. Container
        container = self.container_boot.boot_container()
        self.service_registry.register_service("Container", container)
        container.register("Configuration", instance=config)
        container.register("Database", instance=db_manager)

        from toji_platform.core.configuration.manager import ConfigurationManager
        from toji_platform.core.configuration.interfaces import IConfigProvider
        config_provider = ConfigurationManager(overrides=config)
        container.register(IConfigProvider, instance=config_provider)
        container.register("IConfigProvider", instance=config_provider)

        # 4. EventBus
        event_bus = self.eventbus_boot.boot_eventbus()
        self.service_registry.register_service("EventBus", event_bus)
        container.register("IEventBus", instance=event_bus)
        from toji_platform.core.event_bus.interfaces import IEventBus
        container.register(IEventBus, instance=event_bus)

        # 5. Plugin Loader & Auto Discovery
        plugins = self.plugin_loader.discover_plugins(container)

        # Sort plugins based on defined boot priorities
        boot_priority = {
            # R51–R53 must boot before all domain plugins
            "ConfigPlugin": 0,
            "LoggingPlugin": 1,
            "AlertingPlugin": 1.5,
            "ValidationPlugin": 2,
            "MetricsPlugin": 2.5,
            # Domain plugins
            "ConfigurationPlugin": 3,
            "ResearchDataPlatformPlugin": 5,
            "InstitutionalMemoryPlugin": 8,
            "KnowledgeGraphPlugin": 9,
            "FeaturePlatformPlugin": 10,
            "PriceActionPlugin": 10.1,
            "MultiTimeframePlugin": 10.2,
            "ConfluencePlugin": 10.3,
            "AISignalPlugin": 10.4,
            "RiskManagementPlugin": 11,
            "RiskEngineV2Plugin": 11.5,
            "PositionSizingPlugin": 11.8,
            "TradeJournalPlugin": 12,
            "OmsPlugin": 13,
            "ExecutionEnginePlugin": 14,
            "BacktestingEnginePlugin": 15,
            "OptimizationEnginePlugin": 16,
            "PaperMarketPlugin": 17,
            "PaperTradingPlugin": 18,
            "PaperDashboardPlugin": 19,
            "OperationsCenterPlugin": 20,
            "PortfolioAnalyticsPlugin": 21,
            "PortfolioIntelligencePlugin": 21.5,
            "StrategyLifecyclePlugin": 22,
            "StrategyFrameworkPlugin": 22.5,
            "ExperimentManagerPlugin": 23,
            "StrategySchedulerPlugin": 24,
            "StressTestingPlugin": 25,
            "MonitoringPlugin": 26,
            "ReportingPlugin": 27,
            "TOJIOSPlugin": 28,
            "LiveTradingEnginePlugin": 29,
            "PortfolioGovernorPlugin": 28.5,
            "PortfolioAccountingPlugin": 29.5,
            "ExitEnginePlugin": 29.7,
            "RecoveryPlugin": 30,
            "RuntimePlugin": 31,
        }

        def get_priority(plugin_instance: Any) -> int:
            class_name = plugin_instance.__class__.__name__
            return boot_priority.get(class_name, 30)

        sorted_plugins = sorted(plugins, key=get_priority)

        # 6. Boot Subsystem Plugins sequentially
        #
        # Critical trading dependency plugins are those whose absence leaves the runtime
        # unable to execute orders safely. Derived from actual dependency trace:
        #
        #   OmsPlugin (priority 13)
        #     → registers OmsCore → required by tick loop oms_core.submit_order()
        #   PaperMarketPlugin (priority 17)
        #     → registers PaperExecutionRouter → required by OmsCore._get_execution_router()
        #   PaperTradingPlugin (priority 18)
        #     → registers PaperTradingOrchestrator → required by PaperExecutionRouter
        #   PortfolioAccountingPlugin (priority 29.5)
        #     → registers AccountingService → required for risk state resolution (fail-closed)
        #
        # If any critical plugin fails to initialize:
        #   - Trading is halted (TradingHalted flag registered in container)
        #   - All non-critical plugins continue booting (observability, alerting, etc.)
        #   - The runtime tick loop MUST check the TradingHalted flag before submitting orders
        #
        CRITICAL_PLUGIN_NAMES: frozenset = frozenset({
            "OmsPlugin",
            "PaperMarketPlugin",
            "PaperTradingPlugin",
            "PortfolioAccountingPlugin",
        })

        _failed_plugins: list = []
        _critical_failed_plugins: list = []
        _trading_halted = False

        for p in sorted_plugins:
            plugin_name = p.__class__.__name__
            is_critical = plugin_name in CRITICAL_PLUGIN_NAMES
            logger.info("Booting Subsystem Plugin: %s (critical=%s)", plugin_name, is_critical)
            try:
                p.initialize()
            except Exception as _plugin_err:
                if is_critical:
                    _trading_halted = True
                    _critical_failed_plugins.append(plugin_name)
                    logger.error(
                        "CRITICAL PLUGIN BOOT FAILURE [%s]: %s — trading halted for safety.",
                        plugin_name, _plugin_err,
                        exc_info=True
                    )
                else:
                    logger.error(
                        "Plugin boot failure [%s]: %s — platform continues without this plugin.",
                        plugin_name, _plugin_err,
                        exc_info=True
                    )
                _failed_plugins.append(plugin_name)

        if _critical_failed_plugins:
            logger.critical(
                "PLATFORM BOOT: TRADING HALTED. %d critical plugin(s) failed: %s",
                len(_critical_failed_plugins), ", ".join(_critical_failed_plugins)
            )
        if _failed_plugins:
            non_critical_failed = [p for p in _failed_plugins if p not in _critical_failed_plugins]
            if non_critical_failed:
                logger.warning(
                    "PLATFORM BOOT: %d non-critical plugin(s) failed: %s",
                    len(non_critical_failed), ", ".join(non_critical_failed)
                )
        else:
            logger.info("PLATFORM BOOT: all plugins initialized successfully.")

        # Register boot outcomes in DI container for runtime access
        self.service_registry.register_service("Plugins", sorted_plugins)
        self.service_registry.register_service("FailedPlugins", _failed_plugins)
        self.service_registry.register_service("CriticalFailedPlugins", _critical_failed_plugins)
        container.register("TradingHalted", instance=_trading_halted)
        container.register("FailedPlugins", instance=_failed_plugins)
        container.register("CriticalFailedPlugins", instance=_critical_failed_plugins)

        # Run startup validation pass after all subsystems are fully booted and registered
        try:
            if container.has("ValidationOrchestrator"):
                logger.info("Running platform post-boot startup validation...")
                orchestrator = container.resolve("ValidationOrchestrator")
                from research_platform.validation.models import ValidationDuration
                run = orchestrator.run_all(duration=ValidationDuration.QUICK)
                cert = orchestrator.get_latest_certification()
                if cert:
                    logger.info("Post-boot startup validation: %s", cert.summary)
        except Exception as e:
            logger.warning("Post-boot startup validation failed: %s", e)

        logger.info("TOJI V1 Platform Boot Sequence Completed successfully.")
