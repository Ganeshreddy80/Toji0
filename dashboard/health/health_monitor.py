"""Health Monitor for tracking the status and latencies of all subsystems."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Dict

from dashboard.core.enums import HealthStatus
from dashboard.core.models import SubsystemHealth

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Tracks status, message counts, and event latencies for platform subsystems."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        
        # Tracked subsystems list
        self._subsystems = ["MIL", "PAE", "PQE", "CE", "SE", "TC", "RE", "PSE"]
        
        # Health status mappings
        self._health: Dict[str, SubsystemHealth] = {}
        
        now = datetime.now(timezone.utc)
        for sub in self._subsystems:
            self._health[sub] = SubsystemHealth(
                status=HealthStatus.INITIALIZING,
                last_update=now,
                processing_latency_ms=0.0,
                message_count=0,
                replay_status="LIVE",
            )

    def register_message(self, subsystem: str, latency_ms: float) -> None:
        """Record an event message update for a subsystem, updating counters and latencies."""
        with self._lock:
            if subsystem not in self._health:
                # Dynamically register any untracked custom subsystem
                self._health[subsystem] = SubsystemHealth(
                    status=HealthStatus.HEALTHY,
                    last_update=datetime.now(timezone.utc),
                    processing_latency_ms=latency_ms,
                    message_count=1,
                    replay_status="LIVE",
                )
                return

            current = self._health[subsystem]
            new_count = current.message_count + 1
            
            # Simple rolling average for processing latency
            new_latency = ((current.processing_latency_ms * current.message_count) + latency_ms) / new_count

            # Shift status from INITIALIZING to HEALTHY when first message is received
            new_status = HealthStatus.HEALTHY
            if current.status == HealthStatus.ERROR:
                new_status = HealthStatus.ERROR  # Keep error status if explicitly set

            self._health[subsystem] = SubsystemHealth(
                status=new_status,
                last_update=datetime.now(timezone.utc),
                processing_latency_ms=new_latency,
                message_count=new_count,
                replay_status=current.replay_status,
            )

    def set_status(self, subsystem: str, status: HealthStatus, replay_status: str | None = None) -> None:
        """Manually override a subsystem status."""
        with self._lock:
            if subsystem in self._health:
                current = self._health[subsystem]
                self._health[subsystem] = SubsystemHealth(
                    status=status,
                    last_update=datetime.now(timezone.utc),
                    processing_latency_ms=current.processing_latency_ms,
                    message_count=current.message_count,
                    replay_status=replay_status or current.replay_status,
                )

    def get_health_status(self) -> Dict[str, SubsystemHealth]:
        """Retrieve copy of all tracked subsystem health states."""
        with self._lock:
            return dict(self._health)
