"""TojiKernel — the main orchestrator for the Toji platform.

The kernel ties together every core subsystem:
configuration, logging, event bus, registries, plugins,
lifecycle management, and dependency injection.

Usage::

    kernel = TojiKernel()
    kernel.boot()
    # ... platform is running ...
    kernel.shutdown()
"""

from __future__ import annotations

import enum
import logging
import threading

from toji_platform.core.configuration import ConfigurationManager, IConfigProvider
from toji_platform.core.dependency_injection import Container, IContainer
from toji_platform.core.event_bus import IEventBus, InMemoryEventBus
from toji_platform.core.lifecycle import LifecycleManager, HeartbeatScheduler
from toji_platform.core.logging import StructuredLogger, get_logger
from toji_platform.core.plugin_manager import IPluginManager, PluginManager
from toji_platform.core.registry import (
    AgentRegistry,
    AnalyticsProviderRegistry,
    AssetRegistry,
    MemoryProviderRegistry,
    PlaybookRegistry,
    PluginRegistry,
    ResearchModuleRegistry,
    StrategyRegistry,
)
from toji_platform.core.types import HealthStatus, Profile


class KernelState(enum.Enum):
    """Execution state of the TojiKernel."""

    STOPPED = "stopped"
    BOOTING = "booting"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    FAILED = "failed"


class TojiKernel:
    """Central kernel that bootstraps and manages all platform services.

    The boot sequence:

    1. Load configuration (env vars + overrides).
    2. Initialise structured logging.
    3. Create the DI container and register core services.
    4. Create the event bus.
    5. Create all domain registries.
    6. Create the plugin manager.
    7. Run lifecycle startup on all registered components.
    """

    def __init__(
        self,
        config_overrides: dict[str, object] | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._state = KernelState.STOPPED
        self._booted = False
        self.restart_count = 0
        self.exception_count = 0

        # 1. Configuration
        self._config = ConfigurationManager(overrides=config_overrides)

        # 2. Logging
        log_level_name = str(
            self._config.get("app.log.level", "INFO")
        ).upper()
        log_level = getattr(logging, log_level_name, logging.INFO)
        json_logs = self._config.profile == Profile.PRODUCTION
        self._logger: StructuredLogger = get_logger(
            "toji.kernel", level=log_level, json_output=json_logs
        )

        # 3. DI Container
        self._container = Container()

        # 4. Event Bus
        self._event_bus = InMemoryEventBus()

        # 5. Registries
        self._research_registry = ResearchModuleRegistry()
        self._agent_registry = AgentRegistry()
        self._playbook_registry = PlaybookRegistry()
        self._plugin_registry = PluginRegistry()
        self._strategy_registry = StrategyRegistry()
        self._asset_registry = AssetRegistry()
        self._memory_provider_registry = MemoryProviderRegistry()
        self._analytics_provider_registry = AnalyticsProviderRegistry()

        # 6. Plugin Manager
        self._plugin_manager = PluginManager()

        # 7. Lifecycle Manager
        self._lifecycle = LifecycleManager()

        # 8. Heartbeat Scheduler
        self._heartbeat_scheduler = HeartbeatScheduler(
            event_bus=self._event_bus,
            plugin_manager=self._plugin_manager
        )
        self._lifecycle.register(self._heartbeat_scheduler)

        # 9. Health Monitor
        from toji_platform.services.health_monitor import RuntimeHealthMonitor
        self._health_monitor = RuntimeHealthMonitor(self)
        self._lifecycle.register(self._health_monitor)

        # 10. Alert Manager
        from toji_platform.services.alert_manager import AlertManager
        self._alert_manager = AlertManager(self._health_monitor)

        # Register core services in the container
        self._register_core_services()

    # ── Boot / Shutdown ────────────────────────────────────────────────

    def boot(self) -> None:
        """Execute the full boot sequence."""
        with self._lock:
            if self._state == KernelState.RUNNING:
                self._logger.warning("Kernel already booted — skipping")
                return
            if self._state == KernelState.BOOTING:
                self._logger.warning("Kernel is booting — skipping")
                return
            if self._state == KernelState.SHUTTING_DOWN:
                raise RuntimeError("Cannot boot while shutting down")

            self._logger.info(
                "Toji Kernel booting",
                profile=self._config.profile.value,
            )

            self._state = KernelState.BOOTING
            self._booted = False

            try:
                # Validate minimum configuration
                self._validate_config()

                # Initialise plugins (topological order)
                self._plugin_manager.initialize_all()

                # Start lifecycle-managed components
                self._lifecycle.start_all()
            except Exception:
                self._state = KernelState.FAILED
                self._booted = False
                self.exception_count += 1
                self._kernel_rollback()
                raise

            self._state = KernelState.RUNNING
            self._booted = True
            self._logger.info("Toji Kernel boot complete ✓")

    def _kernel_rollback(self) -> None:
        """Safely roll back partially started lifecycle components and initialized plugins."""
        self._logger.info("Kernel boot failed — initiating cleanup rollback")

        # 1. Stop lifecycle components safely
        try:
            self._lifecycle.stop_all()
        except Exception as exc:
            self._logger.error(f"Error during lifecycle rollback stopping: {exc}")

        # 2. Shutdown plugins safely
        try:
            self._plugin_manager.shutdown_all()
        except Exception as exc:
            self._logger.error(f"Error during plugin manager rollback shutdown: {exc}")

    def shutdown(self) -> None:
        """Gracefully shut down the platform."""
        with self._lock:
            if self._state == KernelState.STOPPED:
                self._logger.warning("Kernel not booted — nothing to shut down")
                return
            if self._state == KernelState.SHUTTING_DOWN:
                self._logger.warning("Kernel is shutting down — skipping")
                return
            if self._state == KernelState.BOOTING:
                raise RuntimeError("Cannot shutdown while booting")

            self._logger.info("Toji Kernel shutting down")
            self._state = KernelState.SHUTTING_DOWN

            try:
                # Shutdown plugins (reverse order)
                self._plugin_manager.shutdown_all()

                # Stop lifecycle components (reverse order)
                self._lifecycle.stop_all()

                # Clear EventBus subscriptions to release handler references
                self._event_bus.clear()
            except Exception:
                self.exception_count += 1
                raise
            finally:
                self._state = KernelState.STOPPED
                self._booted = False

            self._logger.info("Toji Kernel shut down ✓")

    def restart(self) -> None:
        """Atomically shut down and reboot the kernel."""
        with self._lock:
            self._logger.info("Toji Kernel restarting")
            self.restart_count += 1
            try:
                if self._state not in (KernelState.STOPPED, KernelState.FAILED):
                    self.shutdown()
            except Exception as exc:
                self.exception_count += 1
                self._logger.error("Error during restart shutdown phase: %s", exc)
                raise
            self.boot()

    # ── Health ─────────────────────────────────────────────────────────

    def health_check(self) -> dict[str, HealthStatus]:
        """Aggregate health status from lifecycle + plugins."""
        results: dict[str, HealthStatus] = {}
        results.update(self._lifecycle.health_check())
        results.update(self._plugin_manager.health_check_all())
        return results

    # ── Accessors ──────────────────────────────────────────────────────

    @property
    def is_booted(self) -> bool:
        return self._booted

    @property
    def state(self) -> KernelState:
        """Return the current execution state of the kernel."""
        with self._lock:
            return self._state

    @property
    def restart_count_value(self) -> int:
        """Return the current restart count of the kernel."""
        with self._lock:
            return self.restart_count

    @property
    def exception_count_value(self) -> int:
        """Return the current exception count of the kernel."""
        with self._lock:
            return self.exception_count

    @property
    def config(self) -> IConfigProvider:
        return self._config

    @property
    def container(self) -> IContainer:
        return self._container

    @property
    def event_bus(self) -> IEventBus:
        return self._event_bus

    @property
    def plugin_manager(self) -> IPluginManager:
        return self._plugin_manager

    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    @property
    def health_monitor(self) -> RuntimeHealthMonitor:
        from toji_platform.services.health_monitor import RuntimeHealthMonitor
        return self._health_monitor

    @property
    def alert_manager(self) -> AlertManager:
        from toji_platform.services.alert_manager import AlertManager
        return self._alert_manager

    @property
    def research_registry(self) -> ResearchModuleRegistry:
        return self._research_registry

    @property
    def agent_registry(self) -> AgentRegistry:
        return self._agent_registry

    @property
    def playbook_registry(self) -> PlaybookRegistry:
        return self._playbook_registry

    @property
    def plugin_registry(self) -> PluginRegistry:
        return self._plugin_registry

    @property
    def strategy_registry(self) -> StrategyRegistry:
        return self._strategy_registry

    @property
    def asset_registry(self) -> AssetRegistry:
        return self._asset_registry

    @property
    def memory_provider_registry(self) -> MemoryProviderRegistry:
        return self._memory_provider_registry

    @property
    def analytics_provider_registry(self) -> AnalyticsProviderRegistry:
        return self._analytics_provider_registry

    # ── Internal helpers ───────────────────────────────────────────────

    def _register_core_services(self) -> None:
        """Populate the DI container with core kernel services."""
        self._container.register(IConfigProvider, instance=self._config)
        self._container.register(IEventBus, instance=self._event_bus)
        self._container.register(IPluginManager, instance=self._plugin_manager)
        self._container.register(IContainer, instance=self._container)
        self._container.register(
            "lifecycle_manager", instance=self._lifecycle
        )
        self._container.register(
            "heartbeat_scheduler", instance=self._heartbeat_scheduler
        )
        self._container.register(
            "research_registry", instance=self._research_registry
        )
        self._container.register(
            "agent_registry", instance=self._agent_registry
        )
        self._container.register(
            "playbook_registry", instance=self._playbook_registry
        )
        self._container.register(
            "plugin_registry", instance=self._plugin_registry
        )
        self._container.register(
            "strategy_registry", instance=self._strategy_registry
        )
        self._container.register(
            "asset_registry", instance=self._asset_registry
        )
        self._container.register(
            "memory_provider_registry",
            instance=self._memory_provider_registry,
        )
        self._container.register(
            "analytics_provider_registry",
            instance=self._analytics_provider_registry,
        )
        from toji_platform.services.health_monitor import RuntimeHealthMonitor
        self._container.register(
            RuntimeHealthMonitor, instance=self._health_monitor
        )
        self._container.register(
            "health_monitor", instance=self._health_monitor
        )
        from toji_platform.services.alert_manager import AlertManager
        self._container.register(
            AlertManager, instance=self._alert_manager
        )
        self._container.register(
            "alert_manager", instance=self._alert_manager
        )

    def _validate_config(self) -> None:
        """Run minimal startup config validation."""
        self._logger.debug("Validating kernel configuration")
        # No hard requirements at kernel level — modules declare
        # their own required keys when they register with the kernel.
