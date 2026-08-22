"""Latency engine simulating network transmission delays.
"""

from __future__ import annotations

import time


class LatencyEngine:
    """Simulates millisecond latency buffers."""

    def simulate_delay(self, environment: str = "PRODUCTION") -> float:
        # Default production execution latency 1.5ms
        delay = 0.0015 if environment == "PRODUCTION" else 0.005
        time.sleep(delay)
        return delay
