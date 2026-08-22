"""Runtime Health Monitor implementation for TOJI platform."""

from __future__ import annotations

import logging
import os
import sys
import threading
import resource
from datetime import datetime, timezone
from typing import Any, Optional

from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.types import HealthStatus

logger = logging.getLogger(__name__)


class RuntimeHealthMonitor(ILifecycle, IHealthCheck):
    """Runtime Health Monitor collects and exposes system/platform health metrics."""

    def __init__(self, kernel: Any) -> None:
        self._kernel = kernel
        self._running = False
        self._start_time: Optional[datetime] = None
        self._last_heartbeat_time: Optional[datetime] = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "Runtime Health Monitor"

    def start(self) -> None:
        """Start the health monitor and subscribe to heartbeat events."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._start_time = datetime.now(timezone.utc)

        if self._kernel and hasattr(self._kernel, "event_bus") and self._kernel.event_bus:
            try:
                self._kernel.event_bus.subscribe("system.heartbeat", self._on_heartbeat)
            except Exception as exc:
                logger.error("HealthMonitor: Failed to subscribe to system.heartbeat: %s", exc)

        logger.info("Runtime Health Monitor started ✓")

    def stop(self) -> None:
        """Stop the health monitor and unsubscribe from heartbeat events."""
        with self._lock:
            self._running = False

        if self._kernel and hasattr(self._kernel, "event_bus") and self._kernel.event_bus:
            try:
                self._kernel.event_bus.unsubscribe("system.heartbeat", self._on_heartbeat)
            except Exception:
                pass

        logger.info("Runtime Health Monitor stopped ✓")

    def check_health(self) -> HealthStatus:
        """Aggregate monitor self-health status."""
        with self._lock:
            if not self._running:
                return HealthStatus.UNHEALTHY
        return HealthStatus.HEALTHY

    def _on_heartbeat(self, event: Any) -> None:
        """Heartbeat listener callback."""
        with self._lock:
            self._last_heartbeat_time = datetime.now(timezone.utc)

    def get_health_report(self) -> dict[str, Any]:
        """Collect and return the complete operational health report."""
        import sys

        # 1. Kernel State
        kernel_state = "stopped"
        restart_count = 0
        total_exceptions = 0
        if self._kernel:
            k_state = getattr(self._kernel, "state", None)
            if k_state and hasattr(k_state, "value"):
                kernel_state = k_state.value
            else:
                kernel_state = "unknown"
            restart_count = getattr(self._kernel, "restart_count", 0)
            total_exceptions = getattr(self._kernel, "exception_count", 0)

        # 2. Plugin States
        plugin_states = {}
        if self._kernel and hasattr(self._kernel, "plugin_manager") and self._kernel.plugin_manager:
            try:
                for p in self._kernel.plugin_manager.list_plugins():
                    plugin_states[str(p.plugin_id)] = p.state.value
            except Exception:
                pass

        # 3. Uptime
        uptime = 0.0
        with self._lock:
            if self._start_time:
                uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        # 4. Exception count from event bus
        bus_exceptions = 0
        if self._kernel and hasattr(self._kernel, "event_bus") and self._kernel.event_bus:
            bus_exceptions = getattr(self._kernel.event_bus, "exception_count", 0)

        # Combine kernel and bus exceptions
        exception_count = total_exceptions + bus_exceptions

        # 5. Active thread count
        active_threads = threading.active_count()

        # 6. Memory usage
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        if sys.platform == "darwin":
            memory_rss_mb = rusage.ru_maxrss / (1024 * 1024)
        else:
            memory_rss_mb = rusage.ru_maxrss / 1024

        # 7. CPU usage
        times = os.times()
        cpu_percent = round((times.user + times.system) * 100.0 / max(times.elapsed, 0.01), 2)

        # 8. Lifecycle status
        lifecycle_status = {}
        if self._kernel and hasattr(self._kernel, "lifecycle") and self._kernel.lifecycle:
            try:
                for comp in self._kernel.lifecycle._components:
                    lifecycle_status[comp.name] = (
                        "running" if getattr(comp, "_running", False)
                        or getattr(comp, "_started", False)
                        or (hasattr(comp, "is_started") and comp.is_started)
                        else "stopped"
                    )
            except Exception:
                pass

        # 9. Heartbeat status
        heartbeat_healthy = False
        last_hb = None
        with self._lock:
            if self._last_heartbeat_time:
                last_hb = self._last_heartbeat_time.isoformat()
                time_since_hb = (datetime.now(timezone.utc) - self._last_heartbeat_time).total_seconds()
                # Unhealthy if we missed heartbeat for more than 5 intervals
                heartbeat_healthy = time_since_hb < 5.0

        # 10. Event Bus Health
        listener_count = 0
        if self._kernel and hasattr(self._kernel, "event_bus") and self._kernel.event_bus:
            bus = self._kernel.event_bus
            handlers = getattr(bus, "_handlers", {})
            listener_count = sum(len(h_list) for h_list in handlers.values())

        event_bus_health = {
            "listener_count": listener_count,
            "publish_failures": bus_exceptions,
            "healthy": bus_exceptions == 0
        }

        return {
            "kernel_state": kernel_state,
            "plugin_states": plugin_states,
            "uptime_seconds": round(uptime, 2),
            "restart_count": restart_count,
            "exception_count": exception_count,
            "active_thread_count": active_threads,
            "memory_usage_mb": round(memory_rss_mb, 2),
            "cpu_usage_percent": cpu_percent,
            "lifecycle_status": lifecycle_status,
            "heartbeat_status": {
                "last_heartbeat": last_hb,
                "healthy": heartbeat_healthy
            },
            "event_bus_health": event_bus_health
        }
