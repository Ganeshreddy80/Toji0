"""R52 Performance Logger — records latency, CPU, and memory metrics.
"""

from __future__ import annotations

import logging
from research_platform.logging.models import PerfRecord
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_perf_logger = logging.getLogger("toji.performance")
if not _perf_logger.handlers:
    _h = create_rotating_file_handler("logs", "performance.log", formatter=StructuredJsonFormatter())
    _perf_logger.addHandler(_h)
    _perf_logger.setLevel(logging.DEBUG)
    _perf_logger.propagate = False


class PerformanceLogger:
    """Emits latency and resource usage records to performance.log."""

    def record(self, operation: str, duration_ms: float, cpu_pct: float = 0.0, memory_mb: float = 0.0) -> None:
        rec = PerfRecord(operation=operation, duration_ms=duration_ms, cpu_pct=cpu_pct, memory_mb=memory_mb)
        _perf_logger.debug(
            "PERF | op=%s | duration_ms=%.3f | cpu=%.1f%% | mem=%.1f MB",
            operation, duration_ms, cpu_pct, memory_mb,
            extra={
                "correlation_id": operation,
                "extra_data": rec.model_dump()
            }
        )
