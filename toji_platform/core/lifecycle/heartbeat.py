"""Heartbeat scheduler and telemetry reporting service."""

from __future__ import annotations

import logging
import resource
import threading
import time
from datetime import datetime, timezone
from typing import Any

from toji_platform.core.event_bus.events import SubsystemHeartbeat
from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.plugin_manager.interfaces import IPluginManager
from toji_platform.core.types import HealthStatus, PluginId

logger = logging.getLogger(__name__)


class HeartbeatScheduler(ILifecycle, IHealthCheck):
    """Periodic telemetry and heartbeat scheduler."""

    def __init__(self, event_bus: IEventBus, plugin_manager: IPluginManager) -> None:
        self._event_bus = event_bus
        self._plugin_manager = plugin_manager
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_heartbeats: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "Heartbeat Scheduler"

    def start(self) -> None:
        """Start the background telemetry loop."""
        if self._thread is not None:
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="toji-heartbeat-scheduler",
            daemon=True
        )
        self._thread.start()
        logger.info("Heartbeat Scheduler started successfully ✓")

    def stop(self) -> None:
        """Stop the background telemetry loop."""
        if self._thread is None:
            return
        
        self._stop_event.set()
        self._thread.join(timeout=3.0)
        self._thread = None
        logger.info("Heartbeat Scheduler stopped successfully ✓")

    def check_health(self) -> HealthStatus:
        """Report scheduler health."""
        if self._thread is not None and self._thread.is_alive():
            return HealthStatus.HEALTHY
        return HealthStatus.UNHEALTHY

    def get_latest_heartbeats(self) -> dict[str, dict[str, Any]]:
        """Retrieve cached heartbeats for REST retrieval."""
        with self._lock:
            return dict(self._latest_heartbeats)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._emit_heartbeats()
            except Exception as e:
                logger.error("Error emitting subsystem heartbeats: %s", e)
            
            # Wait 1.0 second, interruptible by stop event
            self._stop_event.wait(1.0)

    def _emit_heartbeats(self) -> None:
        # Determine process memory usage (RSS in MB)
        # On macOS, maxrss is in bytes. Let's divide by 1024 * 1024 to get MB.
        try:
            maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            memory_mb = maxrss / (1024.0 * 1024.0)
        except Exception:
            memory_mb = 0.0

        plugins = self._plugin_manager.list_plugins()
        stats_map = getattr(self._plugin_manager, "_stats", {})

        for plugin in plugins:
            pid = plugin.plugin_id
            pname = plugin.name
            
            # Extract state details
            pstats = stats_map.get(pid, {})
            status = pstats.get("state", "unknown")
            
            # Determine error count or custom metrics
            error_count = 0
            if pstats.get("initialization_errors"):
                error_count += 1
            
            # Check for custom metrics (e.g. queue size or messages processed if exposed)
            queue_depth = 0
            messages_processed = 0
            latency_ms = 0.0

            # Pull custom metrics from specific plugins if they expose them
            if hasattr(plugin, "_orchestrator") and plugin._orchestrator:
                orch = plugin._orchestrator
                if hasattr(orch, "_queue") and hasattr(orch._queue, "qsize"):
                    try:
                        queue_depth = orch._queue.qsize()
                    except Exception:
                        pass
                if hasattr(orch, "_processed_count"):
                    messages_processed = getattr(orch, "_processed_count", 0)
                if hasattr(orch, "_last_latency_ms"):
                    latency_ms = getattr(orch, "_last_latency_ms", 0.0)

            # Execution Engine specific stats extraction
            if pid == PluginId("execution_engine"):
                if hasattr(plugin, "_order_manager") and plugin._order_manager:
                    queue_depth = len(getattr(plugin._order_manager, "_open_orders", {}))
                if hasattr(plugin, "_fill_manager") and plugin._fill_manager:
                    messages_processed = len(getattr(plugin._fill_manager, "_fills", []))

            # Portfolio Engine specific stats extraction
            if pid == PluginId("portfolio_engine"):
                if hasattr(plugin, "_state_store") and plugin._state_store:
                    # open positions count
                    queue_depth = len(getattr(plugin._state_store, "_open_positions", {}))
                if hasattr(plugin, "_repository") and plugin._repository:
                    # history events size
                    messages_processed = len(getattr(plugin._repository, "_history", []))

            now_iso = datetime.now(timezone.utc).isoformat()
            
            # Update last heartbeat in PluginManager stats cache
            pstats["last_heartbeat"] = now_iso

            heartbeat_data = {
                "module_id": str(pid),
                "module_name": pname,
                "status": status,
                "latency_ms": latency_ms,
                "queue_depth": queue_depth,
                "messages_processed": messages_processed,
                "last_update": now_iso,
                "memory_usage": memory_mb,
                "error_count": error_count,
            }

            # Cache the latest telemetry
            with self._lock:
                self._latest_heartbeats[str(pid)] = heartbeat_data

            # Publish event onto the Event Bus
            try:
                event = SubsystemHeartbeat(
                    source=f"heartbeat.{pid}",
                    payload=heartbeat_data
                )
                self._event_bus.publish(event)
            except Exception as e:
                logger.error("Failed to publish heartbeat for %s: %s", pid, e)
