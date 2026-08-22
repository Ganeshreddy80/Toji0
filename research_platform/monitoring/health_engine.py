"""Health engine evaluating component heartbeats.
"""

from __future__ import annotations

from research_platform.monitoring.models import ServiceStatus


class HealthEngine:
    """Evaluates service check times."""

    def evaluate_heartbeat(self, service_name: str, response_time_ms: float) -> ServiceStatus:
        alive = response_time_ms < 1000.0  # Dead if response time is longer than 1 second
        return ServiceStatus(
            service_name=service_name,
            is_alive=alive,
            response_time_ms=response_time_ms
        )
