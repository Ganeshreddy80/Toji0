"""Thread-safe Benchmark Manager for Multi-Model Comparison (Sprint 11C)."""

from __future__ import annotations

import collections
import logging
import math
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.evaluation_events import BenchmarkCompleted
from self_learning.evaluation_metrics import MetricResult
from self_learning.leaderboard import Leaderboard, LeaderboardEntry
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class BenchmarkResult(BaseModel):
    """Immutable benchmark result comparing multiple models."""

    benchmark_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Benchmark test name.")
    dataset_id: str = Field(..., description="Validation dataset ID used.")
    model_metrics: Dict[str, MetricResult] = Field(default_factory=dict)
    rankings: List[LeaderboardEntry] = Field(default_factory=list)
    statistical_summary: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class BenchmarkManager:
    """Thread-safe manager for orchestrating multi-model benchmarking and statistical comparison."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        leaderboard: Optional[Leaderboard] = None,
        max_benchmarks: int = 100,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._leaderboard = leaderboard or Leaderboard(event_bus=event_bus)
        self._max_benchmarks = max_benchmarks
        # benchmark_id -> BenchmarkResult
        self._benchmarks: Dict[str, BenchmarkResult] = {}

    def run_benchmark(
        self,
        name: str,
        dataset_id: str,
        metrics_by_model: Dict[str, MetricResult],
        primary_metric: str = "accuracy",
    ) -> BenchmarkResult:
        """Benchmark multiple models against a dataset, generating rankings and statistical summary."""
        with self._lock:
            if len(self._benchmarks) >= self._max_benchmarks:
                oldest_id = next(iter(self._benchmarks))
                del self._benchmarks[oldest_id]

            metrics_list = list(metrics_by_model.values())

            # Generate rankings via Leaderboard
            rankings = self._leaderboard.update_ranking(
                leaderboard_name=f"benchmark_{name}",
                metrics_list=metrics_list,
                metric_name=primary_metric,
            )

            # Compute statistical summary
            stats_summary = self._compute_statistics(metrics_list)

            result = BenchmarkResult(
                name=name,
                dataset_id=dataset_id,
                model_metrics=metrics_by_model,
                rankings=rankings,
                statistical_summary=stats_summary,
            )
            self._benchmarks[result.benchmark_id] = result

            top_id = rankings[0].model_id if rankings else "none"
            logger.info("Completed benchmark '%s' (id=%s) comparing %d models", name, result.benchmark_id, len(metrics_by_model))

            if self._event_bus:
                self._event_bus.publish(
                    BenchmarkCompleted(
                        benchmark_id=result.benchmark_id,
                        top_model_id=top_id,
                        model_count=len(metrics_by_model),
                    )
                )
            return result

    def get_benchmark(self, benchmark_id: str) -> Optional[BenchmarkResult]:
        """Retrieve a benchmark result by ID."""
        with self._lock:
            return self._benchmarks.get(benchmark_id)

    def list_benchmarks(self) -> List[BenchmarkResult]:
        """List all completed benchmark results."""
        with self._lock:
            return list(self._benchmarks.values())

    def _compute_statistics(self, metrics_list: List[MetricResult]) -> Dict[str, Dict[str, float]]:
        """Compute mean, std_dev, min, max for numeric metric fields."""
        if not metrics_list:
            return {}

        fields = ["accuracy", "precision", "recall", "f1_score", "val_loss", "inference_latency_ms", "throughput"]
        summary: Dict[str, Dict[str, float]] = {}

        for f in fields:
            vals = [float(getattr(m, f, 0.0)) for m in metrics_list]
            if not vals:
                continue
            mean_val = sum(vals) / len(vals)
            variance = sum((x - mean_val) ** 2 for x in vals) / len(vals)
            std_dev = math.sqrt(variance)

            summary[f] = {
                "mean": round(mean_val, 4),
                "std_dev": round(std_dev, 4),
                "min": round(min(vals), 4),
                "max": round(max(vals), 4),
            }

        return summary

    def clear(self) -> None:
        """Clear stored benchmarks."""
        with self._lock:
            self._benchmarks.clear()
            self._leaderboard.clear()
