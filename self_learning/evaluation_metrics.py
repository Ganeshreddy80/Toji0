"""Thread-safe Bounded Evaluation Metrics Repository (Sprint 11C)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class MetricResult(BaseModel):
    """Immutable evaluation metrics snapshot for a model evaluation."""

    metric_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    evaluation_id: str = Field(..., description="Evaluation task identifier.")
    model_id: str = Field(..., description="Model identifier.")
    dataset_id: str = Field(..., description="Validation dataset identifier.")
    accuracy: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    recall: float = Field(default=0.0, ge=0.0, le=1.0)
    f1_score: float = Field(default=0.0, ge=0.0, le=1.0)
    val_loss: float = Field(default=0.0, ge=0.0)
    confusion_matrix: List[List[int]] = Field(default_factory=list, description="2x2 or NxN confusion matrix.")
    inference_latency_ms: float = Field(default=0.0, ge=0.0, description="Average per-sample latency in ms.")
    throughput: float = Field(default=0.0, ge=0.0, description="Evaluated samples per second.")
    sample_count: int = Field(default=0, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class EvaluationMetricsStore:
    """Thread-safe repository maintaining historical evaluation metrics with bounded capacity."""

    def __init__(self, max_records_per_model: int = 50, max_total_records: int = 1000) -> None:
        self._lock = threading.RLock()
        self._max_per_model = max_records_per_model
        self._max_total = max_total_records
        # model_id -> bounded deque of MetricResult
        self._history: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=self._max_per_model)
        )
        # evaluation_id -> MetricResult
        self._by_eval_id: Dict[str, MetricResult] = {}

    def record_metrics(
        self,
        evaluation_id: str,
        model_id: str,
        dataset_id: str,
        accuracy: float = 0.0,
        precision: float = 0.0,
        recall: float = 0.0,
        f1_score: float = 0.0,
        val_loss: float = 0.0,
        confusion_matrix: Optional[List[List[int]]] = None,
        inference_latency_ms: float = 0.0,
        throughput: float = 0.0,
        sample_count: int = 0,
    ) -> MetricResult:
        """Record an immutable MetricResult."""
        with self._lock:
            if len(self._by_eval_id) >= self._max_total:
                oldest_id = next(iter(self._by_eval_id))
                del self._by_eval_id[oldest_id]

            record = MetricResult(
                evaluation_id=evaluation_id,
                model_id=model_id,
                dataset_id=dataset_id,
                accuracy=max(0.0, min(1.0, accuracy)),
                precision=max(0.0, min(1.0, precision)),
                recall=max(0.0, min(1.0, recall)),
                f1_score=max(0.0, min(1.0, f1_score)),
                val_loss=max(0.0, val_loss),
                confusion_matrix=confusion_matrix or [[0, 0], [0, 0]],
                inference_latency_ms=max(0.0, inference_latency_ms),
                throughput=max(0.0, throughput),
                sample_count=max(0, sample_count),
            )

            self._history[model_id].append(record)
            self._by_eval_id[evaluation_id] = record

            logger.info("Recorded evaluation metrics for model '%s': acc=%.4f, f1=%.4f", model_id, record.accuracy, record.f1_score)
            return record

    def get_latest_metrics(self, model_id: str) -> Optional[MetricResult]:
        """Get most recent metric result for a model."""
        with self._lock:
            history = self._history.get(model_id)
            if not history:
                return None
            return history[-1]

    def get_metrics_by_evaluation_id(self, evaluation_id: str) -> Optional[MetricResult]:
        """Get metric result by evaluation task ID."""
        with self._lock:
            return self._by_eval_id.get(evaluation_id)

    def get_metrics_history(self, model_id: str) -> List[MetricResult]:
        """Get full history of metric results for a model."""
        with self._lock:
            return list(self._history.get(model_id, []))

    def list_all_metrics(self) -> List[MetricResult]:
        """List all stored metric results across all evaluations."""
        with self._lock:
            return list(self._by_eval_id.values())

    def count(self) -> int:
        """Return total count of metric records stored."""
        with self._lock:
            return len(self._by_eval_id)

    def clear(self) -> None:
        """Clear all metric records."""
        with self._lock:
            self._history.clear()
            self._by_eval_id.clear()
