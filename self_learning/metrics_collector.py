"""Thread-safe Bounded Metrics Collector for the Self Learning Engine (Sprint 11B)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class PipelineMetrics(BaseModel):
    """Immutable record of collected execution metrics."""

    metric_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str = Field(..., description="Associated pipeline identifier.")
    duration_seconds: float = Field(default=0.0, ge=0.0)
    accuracy: Optional[float] = Field(default=None)
    loss: Optional[float] = Field(default=None)
    validation_metrics: Dict[str, float] = Field(default_factory=dict)
    throughput: float = Field(default=0.0, ge=0.0, description="Samples processed per second.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class MetricsCollector:
    """Thread-safe metrics collector maintaining bounded metric history."""

    def __init__(self, max_history_per_pipeline: int = 100) -> None:
        self._lock = threading.RLock()
        self._max_history = max_history_per_pipeline
        # pipeline_id -> bounded deque of PipelineMetrics
        self._history: Dict[str, collections.deque] = collections.defaultdict(
            lambda: collections.deque(maxlen=self._max_history)
        )

    def record_metrics(
        self,
        pipeline_id: str,
        duration_seconds: float = 0.0,
        accuracy: Optional[float] = None,
        loss: Optional[float] = None,
        validation_metrics: Optional[Dict[str, float]] = None,
        throughput: float = 0.0,
    ) -> PipelineMetrics:
        """Record a set of metrics for a pipeline."""
        with self._lock:
            record = PipelineMetrics(
                pipeline_id=pipeline_id,
                duration_seconds=max(0.0, duration_seconds),
                accuracy=accuracy,
                loss=loss,
                validation_metrics=validation_metrics or {},
                throughput=max(0.0, throughput),
            )
            self._history[pipeline_id].append(record)
            logger.info("Recorded metrics for pipeline '%s': acc=%s, loss=%s, throughput=%.1f", pipeline_id, accuracy, loss, throughput)
            return record

    def get_metrics(self, pipeline_id: str) -> List[PipelineMetrics]:
        """Return history list of recorded metrics for a pipeline."""
        with self._lock:
            return list(self._history.get(pipeline_id, []))

    def get_latest_metrics(self, pipeline_id: str) -> Optional[PipelineMetrics]:
        """Return the most recent metric entry for a pipeline."""
        with self._lock:
            history = self._history.get(pipeline_id)
            if not history:
                return None
            return history[-1]

    def clear_pipeline(self, pipeline_id: str) -> None:
        """Clear metrics history for a single pipeline."""
        with self._lock:
            if pipeline_id in self._history:
                del self._history[pipeline_id]

    def clear(self) -> None:
        """Clear all metrics history."""
        with self._lock:
            self._history.clear()
