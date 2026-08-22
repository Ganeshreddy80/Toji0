"""Thread-safe System & Service Availability Monitor for Mission Control (Sprint 10B)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import logging
import threading
from typing import Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field

from mission_control.history import HealthTransitionRecord

logger = logging.getLogger(__name__)


class ServiceHealthStatus(str, Enum):
    """Enumeration of service health status states."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class ServiceRegistration(BaseModel):
    """Immutable record of a registered service."""

    service_name: str = Field(..., description="Unique service identifier.")
    service_type: str = Field(default="generic", description="Service category/type.")
    health_status: ServiceHealthStatus = Field(default=ServiceHealthStatus.HEALTHY, description="Current health status.")
    last_heartbeat: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last heartbeat timestamp.",
    )
    heartbeat_latency_ms: float = Field(default=0.0, ge=0.0, description="Heartbeat latency in milliseconds.")
    metadata: Dict[str, str] = Field(default_factory=dict, description="Custom metadata tags.")

    model_config = ConfigDict(frozen=True)


class SystemMonitor:
    """Thread-safe System & Service Availability Monitor tracking health status and transitions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._start_time: datetime = datetime.now(timezone.utc)
        self._services: Dict[str, ServiceRegistration] = {}
        self._failed_services: Set[str] = set()
        self._recovered_services: Set[str] = set()
        self._controller_state: str = "RUNNING"

    def set_controller_state(self, state: str) -> None:
        """Update Mission Control controller state."""
        with self._lock:
            self._controller_state = state

    def get_controller_state(self) -> str:
        """Get current controller state."""
        with self._lock:
            return self._controller_state

    def register_service(
        self,
        service_name: str,
        service_type: str = "generic",
        metadata: Optional[Dict[str, str]] = None,
    ) -> ServiceRegistration:
        """Register a new service or update existing registration."""
        with self._lock:
            reg = ServiceRegistration(
                service_name=service_name,
                service_type=service_type,
                health_status=ServiceHealthStatus.HEALTHY,
                last_heartbeat=datetime.now(timezone.utc),
                metadata=metadata or {},
            )
            self._services[service_name] = reg
            self._failed_services.discard(service_name)
            logger.info("Registered service: %s (%s)", service_name, service_type)
            return reg

    def unregister_service(self, service_name: str) -> bool:
        """Unregister a service."""
        with self._lock:
            if service_name in self._services:
                del self._services[service_name]
                self._failed_services.discard(service_name)
                self._recovered_services.discard(service_name)
                return True
            return False

    def update_health_status(
        self,
        service_name: str,
        new_status: ServiceHealthStatus,
        latency_ms: float = 0.0,
    ) -> Optional[HealthTransitionRecord]:
        """Update service health status and return transition record if state changed."""
        with self._lock:
            existing = self._services.get(service_name)
            if not existing:
                return None

            prev_status = existing.health_status
            updated = ServiceRegistration(
                service_name=service_name,
                service_type=existing.service_type,
                health_status=new_status,
                last_heartbeat=datetime.now(timezone.utc),
                heartbeat_latency_ms=max(0.0, latency_ms),
                metadata=existing.metadata,
            )
            self._services[service_name] = updated

            # Track failures and recoveries
            transition: Optional[HealthTransitionRecord] = None
            if prev_status != new_status:
                transition = HealthTransitionRecord(
                    service_name=service_name,
                    previous_status=prev_status.value,
                    new_status=new_status.value,
                    timestamp=datetime.now(timezone.utc),
                )

                if new_status in (ServiceHealthStatus.UNHEALTHY, ServiceHealthStatus.DEGRADED):
                    self._failed_services.add(service_name)
                    self._recovered_services.discard(service_name)
                elif new_status == ServiceHealthStatus.HEALTHY and prev_status in (ServiceHealthStatus.UNHEALTHY, ServiceHealthStatus.DEGRADED):
                    self._failed_services.discard(service_name)
                    self._recovered_services.add(service_name)

            return transition

    def get_controller_uptime_seconds(self) -> float:
        """Get controller uptime in seconds."""
        with self._lock:
            now = datetime.now(timezone.utc)
            return max(0.0, (now - self._start_time).total_seconds())

    def get_registered_services(self) -> List[ServiceRegistration]:
        """List all registered service registrations."""
        with self._lock:
            return list(self._services.values())

    def get_service(self, service_name: str) -> Optional[ServiceRegistration]:
        """Get registration for a specific service."""
        with self._lock:
            return self._services.get(service_name)

    def get_failed_services(self) -> List[str]:
        """Get list of currently failed or degraded service names."""
        with self._lock:
            return sorted(list(self._failed_services))

    def get_recovered_services(self) -> List[str]:
        """Get list of recently recovered service names."""
        with self._lock:
            return sorted(list(self._recovered_services))

    def get_health_summary(self) -> Dict[str, int]:
        """Get count summary of services per health status state."""
        with self._lock:
            summary = {status.value: 0 for status in ServiceHealthStatus}
            for svc in self._services.values():
                summary[svc.health_status.value] += 1
            return summary
