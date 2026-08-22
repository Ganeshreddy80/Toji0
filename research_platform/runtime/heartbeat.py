"""Heartbeat manager providing CPU, memory, and loop latency logging capabilities.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None


class HeartbeatMonitor:
    """Computes CPU times and memory footprints of the active process."""

    def __init__(self) -> None:
        self.process = psutil.Process(os.getpid()) if psutil else None
        self._last_cpu_time = time.process_time()
        self._last_wall_time = time.time()

    def get_telemetry(self) -> Dict[str, Any]:
        """Measure active CPU utilization and memory footprint."""
        now_cpu = time.process_time()
        now_wall = time.time()
        
        # Calculate CPU usage percentage over interval
        wall_diff = now_wall - self._last_wall_time
        if wall_diff > 0:
            cpu_pct = ((now_cpu - self._last_cpu_time) / wall_diff) * 100.0
        else:
            cpu_pct = 0.0
            
        self._last_cpu_time = now_cpu
        self._last_wall_time = now_wall

        # Memory usage in MB
        if self.process:
            try:
                mem_mb = self.process.memory_info().rss / (1024 * 1024)
            except Exception:
                mem_mb = 0.0
        else:
            mem_mb = 0.0

        return {
            "cpu_pct": round(cpu_pct, 2),
            "memory_mb": round(mem_mb, 2)
        }
