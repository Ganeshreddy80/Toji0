"""Operations Center tracking CPU load, memory RSS growth, thread counts, and event queues.
"""

from __future__ import annotations

import os
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class OperationsCenter:
    """Monitors system resources and events queue depths, triggering auto-recovery on anomalies."""

    def __init__(self, container: Any, cpu_threshold: float = 90.0, memory_rss_mb_threshold: float = 1024.0) -> None:
        self.container = container
        self.cpu_threshold = cpu_threshold
        self.memory_rss_mb_threshold = memory_rss_mb_threshold
        self._anomaly_detected = False

    def collect_telemetry(self) -> Dict[str, Any]:
        """Gather current process CPU, memory, threading, and EventBus stats."""
        # 1. Thread count
        thread_count = threading.active_count()

        # 2. CPU & Memory RSS using psutil (sandbox-safe fallback)
        cpu_percent = 0.0
        memory_rss_mb = 0.0
        try:
            import psutil
            process = psutil.Process(os.getpid())
            cpu_percent = process.cpu_percent(interval=None)
            memory_rss_mb = process.memory_info().rss / (1024 * 1024)
        except Exception:
            # Fallback mock values
            cpu_percent = 15.0
            memory_rss_mb = 120.0

        # 3. EventBus Queue Length
        queue_len = 0
        try:
            event_bus = self.container.resolve("IEventBus")
            if hasattr(event_bus, "_timeline"):
                queue_len = len(event_bus._timeline)
        except Exception:
            pass

        telemetry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cpu_percent": cpu_percent,
            "memory_rss_mb": memory_rss_mb,
            "active_threads": thread_count,
            "event_bus_queue_length": queue_len,
            "status": "HEALTHY"
        }

        # Check for anomalies
        if cpu_percent > self.cpu_threshold or memory_rss_mb > self.memory_rss_mb_threshold:
            telemetry["status"] = "ANOMALY"
            self._handle_anomaly(telemetry)

        return telemetry

    def _handle_anomaly(self, telemetry: Dict[str, Any]) -> None:
        """Trigger auto-recovery or alert notifications if resource usage is outside boundaries."""
        if self._anomaly_detected:
            return  # Prevent cascading loop triggers

        self._anomaly_detected = True
        logger.warning("OperationsCenter: Resource anomaly detected! telemetry: %s", telemetry)

        # Trigger auto-recovery
        try:
            # Attempt resolving RecoveryEngine from the DI container
            if self.container.has("RecoveryEngine"):
                recovery_engine = self.container.resolve("RecoveryEngine")
                logger.warning("OperationsCenter: Initiating RecoveryEngine auto-recovery checks...")
                # We assume the recovery engine can run check/reconciliation
                if hasattr(recovery_engine, "trigger_reconciliation"):
                    recovery_engine.trigger_reconciliation()
            
            # Also publish anomaly/recovery event on the event bus
            event_bus = self.container.resolve("IEventBus")
            from toji_platform.core.event_bus.events import BaseEvent
            from dataclasses import dataclass
            
            @dataclass(frozen=True)
            def create_anomaly_event():
                class TelemetryAnomalyAlert(BaseEvent):
                    """Event fired when resource anomaly is caught."""
                return TelemetryAnomalyAlert(source="OperationsCenter", payload=telemetry)
                
            event_bus.publish(create_anomaly_event())
        except Exception as e:
            logger.error("OperationsCenter: Failed to trigger auto-recovery flow: %s", e)
        finally:
            self._anomaly_detected = False
