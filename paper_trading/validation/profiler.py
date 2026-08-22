"""Thread-safe Performance Profiler for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

from contextlib import contextmanager
import logging
import threading
import time
from typing import Dict, Generator, Optional, Tuple

logger = logging.getLogger(__name__)


class PerformanceProfiler:
    """Thread-safe Performance Profiler measuring wall-clock time, throughput, and section execution statistics."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._section_times: Dict[str, float] = {}
        self._section_counts: Dict[str, int] = {}
        self._is_active: bool = False
        self._start_time: float = 0.0

    def start(self) -> None:
        """Start global profiling timer."""
        with self._lock:
            self._is_active = True
            self._start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop global profiling timer and return total elapsed seconds."""
        with self._lock:
            if not self._is_active:
                return 0.0
            elapsed = time.perf_counter() - self._start_time
            self._is_active = False
            return elapsed

    def record_section(self, section_name: str, duration_seconds: float) -> None:
        """Record execution duration for a named section."""
        with self._lock:
            self._section_times[section_name] = self._section_times.get(section_name, 0.0) + duration_seconds
            self._section_counts[section_name] = self._section_counts.get(section_name, 0) + 1

    @contextmanager
    def profile_section(self, section_name: str) -> Generator[None, None, None]:
        """Context manager measuring execution time for a block section."""
        t0 = time.perf_counter()
        try:
            yield
        finally:
            t1 = time.perf_counter()
            self.record_section(section_name, t1 - t0)

    def calculate_throughput(self, total_operations: int, duration_seconds: float) -> float:
        """Calculate throughput in operations per second."""
        if duration_seconds <= 0.0:
            return 0.0
        return total_operations / duration_seconds

    def benchmark_tick_throughput(
        self,
        tick_processor_func,
        tick_count: int = 10000,
    ) -> Tuple[float, float]:
        """Benchmark tick throughput.

        Returns (throughput_ticks_per_sec: float, elapsed_seconds: float).
        """
        start = time.perf_counter()
        tick_processor_func(tick_count)
        elapsed = time.perf_counter() - start
        throughput = self.calculate_throughput(tick_count, elapsed)
        return throughput, elapsed

    def get_profile_report(self) -> Dict[str, Dict[str, float]]:
        """Get report of profiled sections with total duration, invocation count, and average duration."""
        with self._lock:
            report = {}
            for name, total_time in self._section_times.items():
                count = self._section_counts.get(name, 1)
                report[name] = {
                    "total_seconds": round(total_time, 6),
                    "invocation_count": float(count),
                    "average_seconds": round(total_time / count, 6),
                }
            return report

    def reset(self) -> None:
        """Reset all recorded profiling data."""
        with self._lock:
            self._section_times.clear()
            self._section_counts.clear()
            self._is_active = False
            self._start_time = 0.0
