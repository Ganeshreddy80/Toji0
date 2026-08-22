"""Chaos Injector implementation."""

from __future__ import annotations

import os
import time
import sys
import threading
from typing import Any, Callable

from toji_platform.chaos.validators import is_chaos_permitted
from toji_platform.chaos.registry import registry

class ChaosInjector:
    """Safely monkey-patches system modules to simulate failure scenarios under testing environments."""

    def __init__(self) -> None:
        self._originals: dict[tuple[Any, str], Any] = {}
        self._enabled_scenarios: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def enable_scenario(self, name: str, config: dict[str, Any] | None = None) -> None:
        """Enable a chaos scenario by monkey-patching target components."""
        if not is_chaos_permitted():
            logger = import_logger()
            logger.warning("Chaos: Injection requested but is NOT permitted (TOJI_CHAOS_ENABLED is not set to true)")
            return

        with self._lock:
            if name in self._enabled_scenarios:
                return
            self._enabled_scenarios[name] = config or {}
            self._apply_scenario(name, config or {})

    def disable_scenario(self, name: str) -> None:
        """Disable a chaos scenario and restore original methods."""
        with self._lock:
            if name not in self._enabled_scenarios:
                return
            self._enabled_scenarios.pop(name)
            self._restore_for_scenario(name)

    def reset(self) -> None:
        """Disable all scenarios and restore all patched methods."""
        with self._lock:
            for name in list(self._enabled_scenarios.keys()):
                self._restore_for_scenario(name)
            self._enabled_scenarios.clear()
            self._originals.clear()

    def _patch(self, obj: Any, attr: str, patch_fn: Callable[..., Any]) -> None:
        key = (obj, attr)
        if key not in self._originals:
            self._originals[key] = getattr(obj, attr)
        setattr(obj, attr, patch_fn)

    def _apply_scenario(self, name: str, config: dict[str, Any]) -> None:
        from toji_platform.kernel import TojiKernel
        from toji_platform.core.plugin_manager import PluginManager
        from toji_platform.core.lifecycle import LifecycleManager, HeartbeatScheduler
        from toji_platform.core.event_bus import InMemoryEventBus
        import resource
        import os

        logger = import_logger()
        logger.info("Chaos: Enabling scenario '%s' with config: %s", name, config)

        if name == "plugin_init_failure":
            def patch_initialize_all(instance: Any) -> None:
                from toji_platform.core.errors import PluginLoadError
                raise PluginLoadError("chaos_plugin", "Chaos: plugin init failed")
            self._patch(PluginManager, "initialize_all", patch_initialize_all)

        elif name == "plugin_shutdown_failure":
            def patch_shutdown_all(instance: Any) -> None:
                raise RuntimeError("Chaos: plugin shutdown failed")
            self._patch(PluginManager, "shutdown_all", patch_shutdown_all)

        elif name == "lifecycle_startup_failure":
            def patch_start_all(instance: Any) -> None:
                from toji_platform.core.errors import StartupError
                raise StartupError("Chaos: lifecycle startup failed")
            self._patch(LifecycleManager, "start_all", patch_start_all)

        elif name == "lifecycle_shutdown_failure":
            def patch_stop_all(instance: Any) -> None:
                from toji_platform.core.errors import ShutdownError
                raise ShutdownError("Chaos: lifecycle shutdown failed")
            self._patch(LifecycleManager, "stop_all", patch_stop_all)

        elif name == "event_bus_publish_failure":
            def patch_publish(instance: Any, event: Any) -> None:
                from toji_platform.core.errors import EventBusError
                raise EventBusError("Chaos: event bus publish failed")
            self._patch(InMemoryEventBus, "publish", patch_publish)

        elif name == "event_bus_handler_exception":
            orig_subscribe = InMemoryEventBus.subscribe
            def patch_subscribe(instance: Any, event_type: str, handler: Any) -> None:
                def failing_wrapper(evt: Any) -> None:
                    raise RuntimeError("Chaos: event handler exception")
                orig_subscribe(instance, event_type, failing_wrapper)
            self._patch(InMemoryEventBus, "subscribe", patch_subscribe)

        elif name == "heartbeat_timeout":
            def patch_hb_start(instance: Any) -> None:
                pass
            self._patch(HeartbeatScheduler, "start", patch_hb_start)

        elif name == "kernel_boot_failure":
            def patch_boot(instance: Any) -> None:
                raise RuntimeError("Chaos: kernel boot failed")
            self._patch(TojiKernel, "boot", patch_boot)

        elif name == "kernel_shutdown_failure":
            def patch_shutdown(instance: Any) -> None:
                raise RuntimeError("Chaos: kernel shutdown failed")
            self._patch(TojiKernel, "shutdown", patch_shutdown)

        elif name == "memory_pressure":
            orig_getrusage = resource.getrusage
            class DummyRusage:
                def __init__(self, orig: Any) -> None:
                    self._orig = orig
                @property
                def ru_maxrss(self) -> int:
                    return 2 * 1024 * 1024 * 1024 if sys.platform == "darwin" else 2 * 1024 * 1024
                def __getattr__(self, name: str) -> Any:
                    return getattr(self._orig, name)
            def patch_getrusage(who: int) -> Any:
                res = orig_getrusage(who)
                return DummyRusage(res)
            self._patch(resource, "getrusage", patch_getrusage)

        elif name == "cpu_spike":
            class DummyTimes:
                user = 99.0
                system = 0.0
                elapsed = 100.0
            def patch_times() -> Any:
                return DummyTimes()
            self._patch(os, "times", patch_times)

        elif name == "thread_failure":
            def patch_thread_start(instance: Any) -> None:
                raise RuntimeError("Chaos: thread spawn failed")
            self._patch(threading.Thread, "start", patch_thread_start)

        elif name == "delayed_component_startup":
            orig_start_all = LifecycleManager.start_all
            delay = config.get("delay_seconds", 2.0)
            def patch_delayed_start(instance: Any) -> None:
                time.sleep(delay)
                orig_start_all(instance)
            self._patch(LifecycleManager, "start_all", patch_delayed_start)

        elif name == "delayed_component_shutdown":
            orig_stop_all = LifecycleManager.stop_all
            delay = config.get("delay_seconds", 2.0)
            def patch_delayed_stop(instance: Any) -> None:
                time.sleep(delay)
                orig_stop_all(instance)
            self._patch(LifecycleManager, "stop_all", patch_delayed_stop)

    def _restore_for_scenario(self, name: str) -> None:
        from toji_platform.kernel import TojiKernel
        from toji_platform.core.plugin_manager import PluginManager
        from toji_platform.core.lifecycle import LifecycleManager, HeartbeatScheduler
        from toji_platform.core.event_bus import InMemoryEventBus
        import resource
        import os

        targets = []
        if name == "plugin_init_failure":
            targets = [(PluginManager, "initialize_all")]
        elif name == "plugin_shutdown_failure":
            targets = [(PluginManager, "shutdown_all")]
        elif name == "lifecycle_startup_failure":
            targets = [(LifecycleManager, "start_all")]
        elif name == "lifecycle_shutdown_failure":
            targets = [(LifecycleManager, "stop_all")]
        elif name == "event_bus_publish_failure":
            targets = [(InMemoryEventBus, "publish")]
        elif name == "event_bus_handler_exception":
            targets = [(InMemoryEventBus, "subscribe")]
        elif name == "heartbeat_timeout":
            targets = [(HeartbeatScheduler, "start")]
        elif name == "kernel_boot_failure":
            targets = [(TojiKernel, "boot")]
        elif name == "kernel_shutdown_failure":
            targets = [(TojiKernel, "shutdown")]
        elif name == "memory_pressure":
            targets = [(resource, "getrusage")]
        elif name == "cpu_spike":
            targets = [(os, "times")]
        elif name == "thread_failure":
            targets = [(threading.Thread, "start")]
        elif name == "delayed_component_startup":
            targets = [(LifecycleManager, "start_all")]
        elif name == "delayed_component_shutdown":
            targets = [(LifecycleManager, "stop_all")]

        for obj, attr in targets:
            key = (obj, attr)
            if key in self._originals:
                setattr(obj, attr, self._originals.pop(key))

def import_logger() -> Any:
    import logging
    return logging.getLogger("toji.chaos")

chaos_injector = ChaosInjector()
