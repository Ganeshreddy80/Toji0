"""Metrics Collector generating immutable timestamped metric snapshots (Sprint 12C)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class MetricSnapshot(BaseModel):
    """Immutable timestamped metric measurement snapshot."""

    snapshot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metric_name: str = Field(..., description="Name of the metric.")
    value: float = Field(..., description="Numerical metric value.")
    unit: str = Field(default="count", description="Unit of measurement.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    labels: Dict[str, str] = Field(default_factory=dict, description="Metric metadata labels.")
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class MetricsCollector:
    """Collector generating immutable metric snapshots for system visibility."""

    def collect_snapshot(
        self,
        metric_name: str,
        value: float,
        unit: str = "count",
        labels: Optional[Dict[str, str]] = None,
    ) -> MetricSnapshot:
        """Create and return a single timestamped MetricSnapshot."""
        snapshot = MetricSnapshot(
            metric_name=metric_name,
            value=float(value),
            unit=unit,
            labels=labels or {},
        )
        logger.debug("Collected metric snapshot '%s' = %f %s", metric_name, value, unit)
        return snapshot

    def collect_system_metrics(
        self,
        cpu_utilization: float = 25.0,
        memory_utilization: float = 40.0,
        disk_utilization: float = 55.0,
        network_throughput_mbps: float = 120.0,
        deployment_count: int = 1,
        service_health_pct: float = 100.0,
        application_latency_ms: float = 12.5,
        request_throughput_rps: float = 450.0,
        extra_labels: Optional[Dict[str, str]] = None,
    ) -> List[MetricSnapshot]:
        """Collect a full batch of standard system metric snapshots."""
        labels = extra_labels or {"environment": "advisory"}

        snapshots = [
            self.collect_snapshot("cpu_utilization", cpu_utilization, "percent", labels),
            self.collect_snapshot("memory_utilization", memory_utilization, "percent", labels),
            self.collect_snapshot("disk_utilization", disk_utilization, "percent", labels),
            self.collect_snapshot("network_throughput", network_throughput_mbps, "mbps", labels),
            self.collect_snapshot("deployment_count", float(deployment_count), "count", labels),
            self.collect_snapshot("service_health", service_health_pct, "percent", labels),
            self.collect_snapshot("application_latency", application_latency_ms, "ms", labels),
            self.collect_snapshot("request_throughput", request_throughput_rps, "rps", labels),
        ]
        logger.info("Collected batch of %d system metrics", len(snapshots))
        return snapshots
