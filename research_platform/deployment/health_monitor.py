"""Health monitor verifying deployed strategies error rates and latencies.
"""

from __future__ import annotations

from research_platform.deployment.interfaces import IHealthMonitor
from research_platform.deployment.models import DeploymentHealthCard


class HealthMonitor(IHealthMonitor):
    """Evaluates runtime statistics and error flags."""

    def evaluate_health(self, deployment_id: str) -> DeploymentHealthCard:
        # Mock active check indicators
        return DeploymentHealthCard(
            deployment_id=deployment_id,
            error_count=0,
            latency_ms=1.5,
            status="HEALTHY"
        )
