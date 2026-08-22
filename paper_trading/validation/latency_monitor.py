"""Thread-safe Latency Monitor & Percentile Calculator for Sprint 9C Paper Trading Validation."""

from __future__ import annotations

import math
import threading
from typing import Dict, List, Optional


class LatencyMonitor:
    """Thread-safe Latency Monitor tracking tick, candle, processing, and reconnect latency metrics."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._latencies: Dict[str, List[float]] = {
            "tick": [],
            "candle": [],
            "processing": [],
            "reconnect": [],
        }

    def record_latency(self, category: str, latency_ms: float) -> None:
        """Record latency measurement in milliseconds for specified category."""
        if latency_ms < 0.0:
            latency_ms = 0.0

        with self._lock:
            if category not in self._latencies:
                self._latencies[category] = []
            self._latencies[category].append(latency_ms)

    def record_tick_latency(self, latency_ms: float) -> None:
        """Record tick latency measurement in ms."""
        self.record_latency("tick", latency_ms)

    def record_candle_latency(self, latency_ms: float) -> None:
        """Record candle aggregation latency measurement in ms."""
        self.record_latency("candle", latency_ms)

    def record_processing_latency(self, latency_ms: float) -> None:
        """Record tick processing latency measurement in ms."""
        self.record_latency("processing", latency_ms)

    def record_reconnect_latency(self, latency_ms: float) -> None:
        """Record feed reconnection latency measurement in ms."""
        self.record_latency("reconnect", latency_ms)

    def calculate_percentile(self, values: List[float], percentile: float) -> float:
        """Calculate specified percentile (0.0 to 100.0) for a sorted list of float values."""
        if not values:
            return 0.0
        if len(values) == 1:
            return values[0]

        sorted_vals = sorted(values)
        if percentile <= 0.0:
            return sorted_vals[0]
        if percentile >= 100.0:
            return sorted_vals[-1]

        k = (len(sorted_vals) - 1) * (percentile / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        d0 = sorted_vals[int(f)] * (c - k)
        d1 = sorted_vals[int(c)] * (k - f)
        return d0 + d1

    def get_summary_stats(self, category: str = "processing") -> Dict[str, float]:
        """Get summary statistics (average, median, p95, p99, maximum, count) for category."""
        with self._lock:
            vals = list(self._latencies.get(category, []))

        if not vals:
            return {
                "average": 0.0,
                "median": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "maximum": 0.0,
                "count": 0.0,
            }

        sorted_vals = sorted(vals)
        count = len(sorted_vals)
        avg = sum(sorted_vals) / count
        med = self.calculate_percentile(sorted_vals, 50.0)
        p95 = self.calculate_percentile(sorted_vals, 95.0)
        p99 = self.calculate_percentile(sorted_vals, 99.0)
        maximum = sorted_vals[-1]

        return {
            "average": round(avg, 4),
            "median": round(med, 4),
            "p95": round(p95, 4),
            "p99": round(p99, 4),
            "maximum": round(maximum, 4),
            "count": float(count),
        }

    def get_all_summary_stats(self) -> Dict[str, Dict[str, float]]:
        """Get latency statistics summaries for all tracked categories."""
        with self._lock:
            categories = list(self._latencies.keys())

        return {cat: self.get_summary_stats(cat) for cat in categories}

    def reset(self) -> None:
        """Clear all stored latency measurements."""
        with self._lock:
            for cat in self._latencies:
                self._latencies[cat].clear()
