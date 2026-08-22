"""Latency Tracker calculating mean and percentile metrics.
"""

from __future__ import annotations

import numpy as np
from typing import List

from research_platform.observability.models import LatencyMeasurement


class LatencyTracker:
    """Tracks latency lists, compiling P95 and P99 boundaries."""

    @staticmethod
    def calculate_latency(name: str, values: List[float]) -> LatencyMeasurement:
        """Calculate distribution statistics.

        Formula:
            P95 = 95th percentile of latency values
            P99 = 99th percentile of latency values
        """
        if not values:
            return LatencyMeasurement(
                metric_name=name,
                min_ms=0.0,
                max_ms=0.0,
                mean_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0
            )

        arr = np.array(values)
        return LatencyMeasurement(
            metric_name=name,
            min_ms=float(np.min(arr)),
            max_ms=float(np.max(arr)),
            mean_ms=float(np.mean(arr)),
            p95_ms=float(np.percentile(arr, 95.0)),
            p99_ms=float(np.percentile(arr, 99.0))
        )
