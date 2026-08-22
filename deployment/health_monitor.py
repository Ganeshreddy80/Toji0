"""Thread-safe Health Monitor tracking heartbeat, liveness, and readiness (Sprint 12B)."""

from __future__ import annotations

import collections
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ServiceHealthRecord(BaseModel):
    """Immutable health status record for a microservice."""

    service_name: str = Field(..., description="Service identifier name.")
    is_alive: bool = Field(default=True, description="Liveness probe status.")
    is_ready: bool = Field(default=True, description="Readiness probe status.")
    status_message: str = Field(default="Healthy", description="Status details or error message.")
    heartbeat_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class HealthMonitor:
    """Thread-safe Health Monitor maintaining heartbeat records and generating health reports."""

    def __init__(self, max_history_per_service: int = 50, max_services: int = 2000) -> None:
        self._lock = threading.RLock()
        self._max_history = max_history_per_service
        self._max_services = max_services
        # service_name -> latest ServiceHealthRecord
        self._latest: Dict[str, ServiceHealthRecord] = {}
        # service_name -> bounded deque of ServiceHealthRecord
        self._history: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=self._max_history)
        )

    def record_heartbeat(
        self,
        service_name: str,
        is_alive: bool = True,
        is_ready: bool = True,
        status_message: str = "Healthy",
    ) -> ServiceHealthRecord:
        """Record a heartbeat health update for a service."""
        with self._lock:
            if len(self._latest) >= self._max_services and service_name not in self._latest:
                oldest_name = next(iter(self._latest))
                del self._latest[oldest_name]
                del self._history[oldest_name]

            record = ServiceHealthRecord(
                service_name=service_name,
                is_alive=is_alive,
                is_ready=is_ready,
                status_message=status_message,
            )

            self._latest[service_name] = record
            self._history[service_name].append(record)

            logger.debug("Recorded health heartbeat for '%s': alive=%s, ready=%s", service_name, is_alive, is_ready)
            return record

    def get_health(self, service_name: str) -> Optional[ServiceHealthRecord]:
        """Retrieve latest health record for a service."""
        with self._lock:
            return self._latest.get(service_name)

    def get_health_history(self, service_name: str) -> List[ServiceHealthRecord]:
        """Retrieve historical health records for a service."""
        with self._lock:
            return list(self._history.get(service_name, []))

    def is_service_healthy(self, service_name: str) -> bool:
        """Return True if service exists and is both alive and ready."""
        with self._lock:
            rec = self._latest.get(service_name)
            if not rec:
                return False
            return rec.is_alive and rec.is_ready

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate an aggregate advisory health report across all tracked services."""
        with self._lock:
            total = len(self._latest)
            healthy_count = sum(1 for r in self._latest.values() if r.is_alive and r.is_ready)
            degraded_count = total - healthy_count

            details = {
                name: {
                    "is_alive": r.is_alive,
                    "is_ready": r.is_ready,
                    "status": r.status_message,
                    "last_heartbeat": r.heartbeat_timestamp.isoformat(),
                }
                for name, r in self._latest.items()
            }

            return {
                "total_services": total,
                "healthy_services": healthy_count,
                "degraded_services": degraded_count,
                "overall_status": "HEALTHY" if degraded_count == 0 else "DEGRADED",
                "services": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_advisory_only": True,
            }

    def count(self) -> int:
        """Return total count of tracked services."""
        with self._lock:
            return len(self._latest)

    def clear(self) -> None:
        """Clear all health monitoring records."""
        with self._lock:
            self._latest.clear()
            self._history.clear()
