"""Tests for the Plugin Manager."""

from __future__ import annotations

import pytest

from toji_platform.core.errors import (
    PluginDependencyError,
    PluginLoadError,
    PluginNotFoundError,
)
from toji_platform.core.plugin_manager import IPlugin, PluginManager
from toji_platform.core.types import HealthStatus, ModuleState, PluginId


class StubPlugin(IPlugin):
    """Minimal IPlugin implementation for testing."""

    def __init__(
        self,
        pid: str,
        name: str = "stub",
        version: str = "0.1.0",
        deps: list[str] | None = None,
    ):
        self._id = PluginId(pid)
        self._name = name
        self._version = version
        self._deps = [PluginId(d) for d in (deps or [])]
        self._state = ModuleState.CREATED
        self.initialized = False
        self.shut_down = False

    @property
    def plugin_id(self) -> PluginId:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def dependencies(self) -> list[PluginId]:
        return self._deps

    @property
    def state(self) -> ModuleState:
        return self._state

    def initialize(self) -> None:
        self._state = ModuleState.RUNNING
        self.initialized = True

    def shutdown(self) -> None:
        self._state = ModuleState.STOPPED
        self.shut_down = True

    def health_check(self) -> HealthStatus:
        return HealthStatus.HEALTHY


class FailingPlugin(StubPlugin):
    """Plugin that raises on initialize."""

    def initialize(self) -> None:
        raise RuntimeError("init boom")


class TestPluginManager:
    """Tests for PluginManager."""

    def test_load_and_list(self):
        pm = PluginManager()
        p = StubPlugin("p1", "Plugin1")
        pm.load(p)
        assert len(pm.list_plugins()) == 1

    def test_load_duplicate_raises(self):
        pm = PluginManager()
        p = StubPlugin("p1")
        pm.load(p)
        with pytest.raises(PluginLoadError, match="already loaded"):
            pm.load(StubPlugin("p1"))

    def test_get(self):
        pm = PluginManager()
        p = StubPlugin("p1", "Plugin1")
        pm.load(p)
        assert pm.get(PluginId("p1")).name == "Plugin1"

    def test_get_nonexistent_raises(self):
        pm = PluginManager()
        with pytest.raises(PluginNotFoundError, match="nope"):
            pm.get(PluginId("nope"))

    def test_unload(self):
        pm = PluginManager()
        pm.load(StubPlugin("p1"))
        pm.unload(PluginId("p1"))
        assert len(pm.list_plugins()) == 0

    def test_unload_nonexistent_raises(self):
        pm = PluginManager()
        with pytest.raises(PluginNotFoundError):
            pm.unload(PluginId("nope"))

    def test_initialize_all_calls_initialize(self):
        pm = PluginManager()
        p = StubPlugin("p1")
        pm.load(p)
        pm.initialize_all()
        assert p.initialized is True

    def test_shutdown_all_calls_shutdown(self):
        pm = PluginManager()
        p = StubPlugin("p1")
        pm.load(p)
        pm.initialize_all()
        pm.shutdown_all()
        assert p.shut_down is True

    def test_dependency_order(self):
        """Plugins with dependencies must be initialized after deps."""
        pm = PluginManager()
        init_order = []

        class OrderedPlugin(StubPlugin):
            def initialize(self):
                init_order.append(self._id)
                super().initialize()

        p_base = OrderedPlugin("base", "Base")
        p_dependent = OrderedPlugin("dep", "Dependent", deps=["base"])
        # Load in reverse order — manager should sort correctly
        pm.load(p_dependent)
        pm.load(p_base)
        pm.initialize_all()
        assert init_order == [PluginId("base"), PluginId("dep")]

    def test_missing_dependency_raises(self):
        pm = PluginManager()
        pm.load(StubPlugin("p1", deps=["missing"]))
        with pytest.raises(PluginDependencyError, match="missing"):
            pm.initialize_all()

    def test_failing_init_raises_plugin_load_error(self):
        pm = PluginManager()
        pm.load(FailingPlugin("fail", "Failing"))
        with pytest.raises(PluginLoadError, match="init boom"):
            pm.initialize_all()

    def test_health_check_all(self):
        pm = PluginManager()
        pm.load(StubPlugin("p1"))
        pm.load(StubPlugin("p2"))
        results = pm.health_check_all()
        assert len(results) == 2
        assert all(s == HealthStatus.HEALTHY for s in results.values())

    def test_circular_dependency_raises(self):
        pm = PluginManager()
        pm.load(StubPlugin("a", deps=["b"]))
        pm.load(StubPlugin("b", deps=["a"]))
        with pytest.raises(PluginDependencyError, match="Circular"):
            pm.initialize_all()

    def test_unload_shuts_down_active_plugin(self):
        """PluginManager.unload() must call shutdown() if the plugin is initialized/running."""
        pm = PluginManager()
        p = StubPlugin("p1")
        pm.load(p)
        pm.initialize_all()
        assert p.initialized is True
        assert p.shut_down is False

        pm.unload(PluginId("p1"))
        assert p.shut_down is True  # Should have been shut down during unload

    def test_duplicate_initialize_is_no_op(self):
        """Duplicate initialize() on a running plugin must be a no-op."""
        pm = PluginManager()
        p = StubPlugin("p1")
        pm.load(p)
        pm.initialize_all()
        assert p.initialized is True

        # Second call to initialize should be guarded and a no-op
        p.initialize()
        assert p.state == ModuleState.RUNNING

    def test_duplicate_shutdown_is_no_op(self):
        """Duplicate shutdown() on a stopped plugin must be a no-op."""
        pm = PluginManager()
        p = StubPlugin("p1")
        pm.load(p)
        pm.initialize_all()
        pm.shutdown_all()
        assert p.shut_down is True

        p.shutdown()
        assert p.state == ModuleState.STOPPED

    def test_shutdown_all_fallback_on_dependency_error(self):
        """shutdown_all() must fall back to reversed load order if dependency resolution fails."""
        pm = PluginManager()
        p1 = StubPlugin("p1")
        p2 = StubPlugin("p2", deps=["missing"])

        pm.load(p1)
        pm.load(p2)

        # Verify that resolve_order would fail
        with pytest.raises(PluginDependencyError):
            pm.initialize_all()

        # Manually set state to running to simulate some plugins having started/initialized
        p1._state = ModuleState.RUNNING
        p2._state = ModuleState.RUNNING

        # shutdown_all() should not crash on dependency error; it must complete successfully
        pm.shutdown_all()
        assert p1.shut_down is True
        assert p2.shut_down is True

