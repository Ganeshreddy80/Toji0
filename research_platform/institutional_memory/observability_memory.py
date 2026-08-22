"""Observability Memory mapping latencies percentiles and logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from research_platform.institutional_memory.models import MemoryMetadata, ObservabilityMemory


class ObservabilityMemoryAdapter:
    """Formats system execution latency to immutable ObservabilityMemory logs."""

    @staticmethod
    def create_record(
        mean_latency: float,
        p95_latency: float,
        cpu_usage: float,
        memory_used: float,
        parent_ids: List[str] = None
    ) -> ObservabilityMemory:
        meta = MemoryMetadata(
            memory_id=f"mem-obs-{uuid.uuid4()}",
            version=1,
            originating_subsystem="observability",
            originating_event="ObservabilityMetricsCollected",
            author="system",
            lineage_parent_ids=parent_ids or []
        )

        return ObservabilityMemory(
            metadata=meta,
            mean_latency_ms=mean_latency,
            p95_latency_ms=p95_latency,
            cpu_usage_pct=cpu_usage,
            memory_used_mb=memory_used
        )
