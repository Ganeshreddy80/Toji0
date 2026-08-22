"""Tests for the TojiKernel orchestrator and boot sequence."""

from __future__ import annotations

import pytest

from toji_platform.boot import boot_kernel
from toji_platform.core.configuration.interfaces import IConfigProvider
from toji_platform.core.event_bus import AssetSelected, MarketDataUpdated
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.plugin_manager.interfaces import IPluginManager
from toji_platform.core.types import HealthStatus, ModuleState, PluginId
from toji_platform.kernel import TojiKernel


class TestTojiKernel:
    """Tests for the TojiKernel class."""

    def test_kernel_instantiates(self):
        kernel = TojiKernel()
        assert kernel.is_booted is False

    def test_boot_and_shutdown(self):
        kernel = TojiKernel()
        kernel.boot()
        assert kernel.is_booted is True
        kernel.shutdown()
        assert kernel.is_booted is False

    def test_double_boot_is_idempotent(self):
        kernel = TojiKernel()
        kernel.boot()
        kernel.boot()  # should log warning but not crash
        assert kernel.is_booted is True
        kernel.shutdown()

    def test_shutdown_before_boot_is_safe(self):
        kernel = TojiKernel()
        kernel.shutdown()  # should not raise

    def test_config_accessible(self):
        kernel = TojiKernel(config_overrides={"app.name": "toji-test"})
        assert kernel.config.get("app.name") == "toji-test"

    def test_event_bus_is_functional(self):
        kernel = TojiKernel()
        kernel.boot()
        received = []
        kernel.event_bus.subscribe(
            "system.asset_selected", lambda e: received.append(e)
        )
        kernel.event_bus.publish(
            AssetSelected(source="test", payload={"symbol": "AAPL"})
        )
        assert len(received) == 1
        kernel.shutdown()

    def test_registries_are_empty_at_boot(self):
        kernel = TojiKernel()
        kernel.boot()
        assert kernel.research_registry.count() == 0
        assert kernel.agent_registry.count() == 0
        assert kernel.strategy_registry.count() == 0
        assert kernel.asset_registry.count() == 0
        assert kernel.playbook_registry.count() == 0
        assert kernel.plugin_registry.count() == 0
        assert kernel.memory_provider_registry.count() == 0
        assert kernel.analytics_provider_registry.count() == 0
        kernel.shutdown()

    def test_container_has_core_services(self):
        kernel = TojiKernel()
        assert kernel.container.has(IConfigProvider) is True
        assert kernel.container.has(IEventBus) is True
        assert kernel.container.has(IPluginManager) is True
        assert kernel.container.has("lifecycle_manager") is True
        assert kernel.container.has("research_registry") is True
        assert kernel.container.has("agent_registry") is True
        assert kernel.container.has("asset_registry") is True

    def test_health_check_returns_dict(self):
        kernel = TojiKernel()
        kernel.boot()
        health = kernel.health_check()
        assert isinstance(health, dict)
        kernel.shutdown()

    def test_kernel_with_plugin(self):
        """Kernel should correctly initialise a loaded plugin."""
        from tests.unit.platform.test_plugin_manager import StubPlugin

        kernel = TojiKernel()
        plugin = StubPlugin("test_plugin", "TestPlugin")
        kernel.plugin_manager.load(plugin)
        kernel.boot()
        assert plugin.initialized is True
        kernel.shutdown()
        assert plugin.shut_down is True


class TestBootKernel:
    """Tests for the boot_kernel() convenience function."""

    def test_boot_returns_running_kernel(self):
        kernel = boot_kernel()
        assert kernel.is_booted is True
        kernel.shutdown()

    def test_boot_with_overrides(self):
        kernel = boot_kernel(config_overrides={"app.name": "boot-test"})
        assert kernel.config.get("app.name") == "boot-test"
        kernel.shutdown()


class TestKernelBootRecovery:
    """Hardening tests for transactional boot and rollback (KH-01)."""

    def test_plugin_initialization_failure(self):
        """Test 1: Plugin initialization failure rolls back initialized plugins and leaves is_booted False."""
        from tests.unit.platform.test_plugin_manager import StubPlugin
        from toji_platform.core.errors import PluginLoadError

        class FailingInitPlugin(StubPlugin):
            def initialize(self) -> None:
                raise RuntimeError("Init failed")

        kernel = TojiKernel()
        p1 = StubPlugin("p1", "Plugin1")
        p2 = FailingInitPlugin("p2", "Plugin2")

        kernel.plugin_manager.load(p1)
        kernel.plugin_manager.load(p2)

        with pytest.raises(PluginLoadError, match="Init failed"):
            kernel.boot()

        assert kernel.is_booted is False
        assert p1.shut_down is True  # Rollback must shut down successfully initialized plugins
        assert p2.initialized is False

    def test_lifecycle_startup_failure(self):
        """Test 2: Lifecycle component startup failure rolls back started components and plugins, and cleans heartbeat thread."""
        from tests.unit.platform.test_plugin_manager import StubPlugin
        from toji_platform.core.errors import StartupError

        class FailingStartComponent:
            def __init__(self) -> None:
                self.name = "FailingComponent"
                self.started = False
                self.stopped = False

            def start(self) -> None:
                raise RuntimeError("Start failed")

            def stop(self) -> None:
                self.stopped = True

        kernel = TojiKernel()
        p1 = StubPlugin("p1", "Plugin1")
        kernel.plugin_manager.load(p1)

        failing_comp = FailingStartComponent()
        kernel.lifecycle.register(failing_comp)

        with pytest.raises(StartupError, match="Start failed"):
            kernel.boot()

        assert kernel.is_booted is False
        assert p1.shut_down is True  # Plugins must be shut down
        assert failing_comp.stopped is True  # Lifecycle component must be stopped
        # Verify heartbeat thread scheduler is stopped/cleaned up
        assert kernel._heartbeat_scheduler._thread is None

    def test_second_boot_after_failed_boot(self):
        """Test 3: Second boot succeeds after a previously rolled back boot failure."""
        from tests.unit.platform.test_plugin_manager import StubPlugin
        from toji_platform.core.errors import PluginLoadError

        class TogglePlugin(StubPlugin):
            def __init__(self, pid: str, name: str):
                super().__init__(pid, name)
                self.should_fail = True

            def initialize(self) -> None:
                if self.should_fail:
                    self.should_fail = False
                    raise RuntimeError("Temporary failure")
                super().initialize()

        kernel = TojiKernel()
        plugin = TogglePlugin("toggle", "Toggle")
        kernel.plugin_manager.load(plugin)

        # First boot fails
        with pytest.raises(PluginLoadError, match="Temporary failure"):
            kernel.boot()

        assert kernel.is_booted is False
        assert plugin.initialized is False

        # Second boot succeeds
        kernel.boot()
        assert kernel.is_booted is True
        assert plugin.initialized is True

        kernel.shutdown()
        assert kernel.is_booted is False
        assert plugin.shut_down is True

    def test_cleanup_failure(self, caplog):
        """Test 4: Rollback continues and re-raises original error even if cleanup fails."""
        from tests.unit.platform.test_plugin_manager import StubPlugin
        from toji_platform.core.errors import StartupError

        class FailingShutdownPlugin(StubPlugin):
            def shutdown(self) -> None:
                raise RuntimeError("Shutdown failed")

        class FailingStopComponent:
            def __init__(self) -> None:
                self.name = "FailingStopComponent"
                self.started = False
                self.stopped = False

            def start(self) -> None:
                self.started = True

            def stop(self) -> None:
                raise RuntimeError("Stop failed")

        class FailingStartComponent:
            def __init__(self) -> None:
                self.name = "FailingStartComponent"
                self.started = False
                self.stopped = False

            def start(self) -> None:
                raise RuntimeError("Trigger boot failure")

            def stop(self) -> None:
                self.stopped = True

        kernel = TojiKernel()
        plugin = FailingShutdownPlugin("fail_shutdown", "FailingShutdown")
        kernel.plugin_manager.load(plugin)

        stop_comp = FailingStopComponent()
        start_comp = FailingStartComponent()
        kernel.lifecycle.register(stop_comp)
        kernel.lifecycle.register(start_comp)

        with caplog.at_level("ERROR"):
            with pytest.raises(StartupError, match="Trigger boot failure"):
                kernel.boot()

        assert kernel.is_booted is False

        # Verify rollback logged the cleanup failures
        log_text = caplog.text
        assert "Error during lifecycle rollback stopping" in log_text
        assert "Error shutting down plugin" in log_text


class TestKernelStateHardening:
    """Tests for the Kernel State Machine Hardening (KH-03)."""

    def test_state_accessor(self):
        from toji_platform.kernel import KernelState
        kernel = TojiKernel()
        assert kernel.state == KernelState.STOPPED
        kernel.boot()
        assert kernel.state == KernelState.RUNNING
        kernel.shutdown()
        assert kernel.state == KernelState.STOPPED

    def test_invalid_transitions(self):
        from toji_platform.kernel import KernelState
        kernel = TojiKernel()

        # 1. Cannot shutdown while booting
        kernel._state = KernelState.BOOTING
        with pytest.raises(RuntimeError, match="Cannot shutdown while booting"):
            kernel.shutdown()

        # 2. Cannot boot while shutting down
        kernel._state = KernelState.SHUTTING_DOWN
        with pytest.raises(RuntimeError, match="Cannot boot while shutting down"):
            kernel.boot()

    def test_duplicate_lifecycle_operations(self):
        from toji_platform.kernel import KernelState
        kernel = TojiKernel()

        # Double boot is idempotent (logs warning, does not crash)
        kernel.boot()
        assert kernel.state == KernelState.RUNNING
        kernel.boot()
        assert kernel.state == KernelState.RUNNING

        # Double shutdown is idempotent
        kernel.shutdown()
        assert kernel.state == KernelState.STOPPED
        kernel.shutdown()
        assert kernel.state == KernelState.STOPPED

    def test_restart_after_failure(self):
        from tests.unit.platform.test_plugin_manager import StubPlugin
        from toji_platform.core.errors import PluginLoadError
        from toji_platform.kernel import KernelState

        class TogglePlugin(StubPlugin):
            def __init__(self, pid: str, name: str):
                super().__init__(pid, name)
                self.should_fail = True

            def initialize(self) -> None:
                if self.should_fail:
                    self.should_fail = False
                    raise RuntimeError("Temporary failure")
                super().initialize()

        kernel = TojiKernel()
        plugin = TogglePlugin("toggle", "Toggle")
        kernel.plugin_manager.load(plugin)

        # Boot fails, state goes to FAILED
        with pytest.raises(PluginLoadError):
            kernel.boot()
        assert kernel.state == KernelState.FAILED

        # Restart should succeed now (re-attempts boot, which succeeds)
        kernel.restart()
        assert kernel.state == KernelState.RUNNING
        assert kernel.is_booted is True

        kernel.shutdown()
        assert kernel.state == KernelState.STOPPED

    def test_failed_restart(self):
        from tests.unit.platform.test_plugin_manager import StubPlugin
        from toji_platform.core.errors import PluginLoadError
        from toji_platform.kernel import KernelState

        class FailingPlugin(StubPlugin):
            def initialize(self) -> None:
                raise RuntimeError("Permanent failure")

        kernel = TojiKernel()
        plugin = FailingPlugin("fail", "Fail")
        kernel.plugin_manager.load(plugin)

        # Boot succeeds/fails (fails here)
        with pytest.raises(PluginLoadError):
            kernel.boot()
        assert kernel.state == KernelState.FAILED

        # Restart fails, re-raises error, state stays FAILED
        with pytest.raises(PluginLoadError):
            kernel.restart()
        assert kernel.state == KernelState.FAILED

    def test_failed_shutdown_transitions_to_stopped(self):
        """Even if components fail to stop during shutdown, state must transition to STOPPED."""
        from toji_platform.core.errors import ShutdownError
        from toji_platform.kernel import KernelState

        class FailingStopComponent:
            def __init__(self) -> None:
                self.name = "FailingStop"
            def start(self) -> None:
                pass
            def stop(self) -> None:
                raise RuntimeError("Stop fail")

        kernel = TojiKernel()
        comp = FailingStopComponent()
        kernel.lifecycle.register(comp)

        kernel.boot()
        assert kernel.state == KernelState.RUNNING

        # Shutdown raises ShutdownError
        with pytest.raises(ShutdownError):
            kernel.shutdown()

        # State must STILL be STOPPED to prevent being stuck in booted/shutting_down state
        assert kernel.state == KernelState.STOPPED
        assert kernel.is_booted is False

    def test_concurrent_boot_and_shutdown(self):
        import threading
        from toji_platform.kernel import KernelState

        kernel = TojiKernel()
        errors = []

        def run_boot():
            try:
                kernel.boot()
            except Exception as e:
                errors.append(e)

        # Start 5 concurrent boot threads
        threads = [threading.Thread(target=run_boot) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No crashes/errors should have occurred
        assert len(errors) == 0
        assert kernel.state == KernelState.RUNNING

        def run_shutdown():
            try:
                kernel.shutdown()
            except Exception as e:
                errors.append(e)

        # Start 5 concurrent shutdown threads
        threads = [threading.Thread(target=run_shutdown) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert kernel.state == KernelState.STOPPED


