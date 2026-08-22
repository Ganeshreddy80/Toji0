"""Thread-safe Memory Monitor & Leak Detector for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import tracemalloc
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MemoryMonitor:
    """Thread-safe Memory Monitor tracking allocations, peak usage, growth rate, and leak detection."""

    def __init__(self, sample_interval_seconds: float = 1.0) -> None:
        self._lock = threading.RLock()
        self._sample_interval = sample_interval_seconds
        self._samples: List[Tuple[datetime, float]] = []  # (timestamp, memory_mb)
        self._is_tracing: bool = False

    def start(self) -> None:
        """Start memory tracing monitor."""
        with self._lock:
            if not self._is_tracing:
                if not tracemalloc.is_tracing():
                    tracemalloc.start()
                self._is_tracing = True
                self._samples.clear()
                self.record_sample()
                logger.debug("MemoryMonitor started.")

    def stop(self) -> None:
        """Stop memory tracing monitor."""
        with self._lock:
            if self._is_tracing:
                self._is_tracing = False
                logger.debug("MemoryMonitor stopped.")

    def record_sample(self) -> float:
        """Record current memory usage sample in MB."""
        with self._lock:
            now = datetime.now(timezone.utc)
            if tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                mem_mb = current / (1024.0 * 1024.0)
            else:
                mem_mb = 0.0

            self._samples.append((now, mem_mb))
            return mem_mb

    def get_peak_memory_mb(self) -> float:
        """Get peak recorded memory in MB."""
        with self._lock:
            if not self._samples:
                return 0.0
            return max(sample[1] for sample in self._samples)

    def get_average_memory_mb(self) -> float:
        """Get average recorded memory in MB."""
        with self._lock:
            if not self._samples:
                return 0.0
            return sum(sample[1] for sample in self._samples) / len(self._samples)

    def get_allocation_growth_mb(self) -> float:
        """Get total allocation growth in MB from first to last sample."""
        with self._lock:
            if len(self._samples) < 2:
                return 0.0
            first_mem = self._samples[0][1]
            last_mem = self._samples[-1][1]
            return max(0.0, last_mem - first_mem)

    def check_memory_leak(self, growth_rate_threshold_mb_per_sec: float = 1.0) -> Tuple[bool, float]:
        """Check for unbounded memory growth/leak.

        Returns (is_leak_detected: bool, growth_rate_mb_per_sec: float).
        """
        with self._lock:
            if len(self._samples) < 2:
                return False, 0.0

            start_time, first_mem = self._samples[0]
            end_time, last_mem = self._samples[-1]

            elapsed = (end_time - start_time).total_seconds()
            if elapsed <= 0.0:
                return False, 0.0

            growth_rate = (last_mem - first_mem) / elapsed
            is_leak = growth_rate > growth_rate_threshold_mb_per_sec

            if is_leak:
                logger.warning(
                    "Memory leak detected! Growth rate %.4f MB/s exceeds threshold %.4f MB/s",
                    growth_rate,
                    growth_rate_threshold_mb_per_sec,
                )

            return is_leak, max(0.0, growth_rate)

    def get_stats(self) -> Dict[str, float]:
        """Get summary dict of memory metrics under a single lock acquisition."""
        with self._lock:
            if not self._samples:
                return {
                    "peak_mb": 0.0,
                    "average_mb": 0.0,
                    "growth_mb": 0.0,
                    "growth_rate_mb_per_sec": 0.0,
                    "is_leak_detected": 0.0,
                    "sample_count": 0.0,
                }

            mem_vals = [s[1] for s in self._samples]
            peak_mb = max(mem_vals)
            avg_mb = sum(mem_vals) / len(mem_vals)

            first_time, first_mem = self._samples[0]
            last_time, last_mem = self._samples[-1]
            growth_mb = max(0.0, last_mem - first_mem)

            elapsed = (last_time - first_time).total_seconds()
            growth_rate = (last_mem - first_mem) / elapsed if elapsed > 0.0 else 0.0
            is_leak = growth_rate > 1.0

            return {
                "peak_mb": peak_mb,
                "average_mb": avg_mb,
                "growth_mb": growth_mb,
                "growth_rate_mb_per_sec": max(0.0, growth_rate),
                "is_leak_detected": 1.0 if is_leak else 0.0,
                "sample_count": float(len(self._samples)),
            }
