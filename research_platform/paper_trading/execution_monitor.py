"""Execution monitor tracking transaction latencies.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class ExecutionMonitor:
    """Tracks latency gaps and operational execution timing statistics."""

    def record_latency(self, order_id: str, submission_time: float) -> float:
        latency_sec = time.perf_counter() - submission_time
        logger.info("Order '%s' execution roundtrip latency: %.4f ms", order_id, latency_sec * 1000.0)
        return latency_sec
