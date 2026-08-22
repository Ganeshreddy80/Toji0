"""Thread-safe In-Memory Evaluation Report Generator and Store (Sprint 11C)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.evaluation_metrics import MetricResult
from self_learning.promotion_rules import PromotionRecommendation

logger = logging.getLogger(__name__)


class EvaluationReport(BaseModel):
    """Immutable comprehensive advisory evaluation report."""

    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = Field(..., description="Target model identifier.")
    evaluation_id: str = Field(..., description="Associated evaluation task ID.")
    benchmark_summary: Dict[str, Any] = Field(default_factory=dict, description="Benchmarking summary metrics.")
    metrics_summary: MetricResult = Field(..., description="Metrics snapshot.")
    promotion_recommendation: PromotionRecommendation = Field(..., description="Advisory promotion recommendation.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class EvaluationReportStore:
    """Thread-safe repository storing immutable evaluation reports with bounded capacity."""

    def __init__(self, max_reports: int = 500) -> None:
        self._lock = threading.RLock()
        self._max_reports = max_reports
        # report_id -> EvaluationReport
        self._reports: Dict[str, EvaluationReport] = {}
        # model_id -> list of report_ids
        self._model_index: Dict[str, List[str]] = collections.defaultdict(list)

    def create_report(
        self,
        model_id: str,
        evaluation_id: str,
        metrics_summary: MetricResult,
        promotion_recommendation: PromotionRecommendation,
        benchmark_summary: Optional[Dict[str, Any]] = None,
    ) -> EvaluationReport:
        """Create and store an immutable EvaluationReport."""
        with self._lock:
            if len(self._reports) >= self._max_reports:
                oldest_id = next(iter(self._reports))
                self.delete_report(oldest_id)

            report = EvaluationReport(
                model_id=model_id,
                evaluation_id=evaluation_id,
                metrics_summary=metrics_summary,
                promotion_recommendation=promotion_recommendation,
                benchmark_summary=benchmark_summary or {},
            )

            self._reports[report.report_id] = report
            self._model_index[model_id].append(report.report_id)

            logger.info("Generated evaluation report '%s' for model '%s'", report.report_id, model_id)
            return report

    def get_report(self, report_id: str) -> Optional[EvaluationReport]:
        """Retrieve report by ID."""
        with self._lock:
            return self._reports.get(report_id)

    def list_reports(self, model_id: Optional[str] = None) -> List[EvaluationReport]:
        """List reports, optionally filtered by model_id."""
        with self._lock:
            if model_id:
                rids = self._model_index.get(model_id, [])
                return [self._reports[rid] for rid in rids if rid in self._reports]
            return list(self._reports.values())

    def delete_report(self, report_id: str) -> bool:
        """Delete a report by ID."""
        with self._lock:
            report = self._reports.pop(report_id, None)
            if report is None:
                return False
            rids = self._model_index.get(report.model_id, [])
            if report_id in rids:
                rids.remove(report_id)
            return True

    def count(self) -> int:
        """Return total count of stored reports."""
        with self._lock:
            return len(self._reports)

    def clear(self) -> None:
        """Clear all stored reports."""
        with self._lock:
            self._reports.clear()
            self._model_index.clear()
