"""Anomaly Detection identifying latency spikes and memory leaks.
"""

from __future__ import annotations

import numpy as np
from typing import List


class AnomalyDetector:
    """Evaluates metrics to detect system health anomalies."""

    @staticmethod
    def detect_latency_spike(latencies: List[float], threshold_factor: float = 3.0) -> bool:
        """Flags latency spikes exceeding historical mean standard deviation bounds."""
        if len(latencies) < 3:
            return False

        arr = np.array(latencies)
        mean = np.mean(arr[:-1])
        std = np.std(arr[:-1])
        
        # Check if last element is an outlier
        last = latencies[-1]
        bound = mean + (threshold_factor * std)
        
        return bool(last > bound)

