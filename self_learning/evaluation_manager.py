"""Thread-safe Evaluation Manager orchestrating the evaluation pipeline lifecycle (Sprint 11C)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from self_learning.benchmark_manager import BenchmarkManager
from self_learning.evaluation_engine import EvaluationEngine
from self_learning.evaluation_events import (
    EvaluationCancelled,
    EvaluationCompleted,
    EvaluationCreated,
    EvaluationFailed,
    EvaluationStarted,
    PromotionEvaluated,
)
from self_learning.evaluation_metrics import EvaluationMetricsStore, MetricResult
from self_learning.evaluation_reports import EvaluationReport, EvaluationReportStore
from self_learning.leaderboard import Leaderboard
from self_learning.promotion_rules import PromotionCriteria, PromotionRecommendation, PromotionRuleEngine
from self_learning.validation_manager import ValidationManager
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class EvaluationStatus(str, Enum):
    """Lifecycle state of an evaluation task."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EvaluationRecord(BaseModel):
    """Immutable state record of an evaluation task execution."""

    evaluation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    model_id: str = Field(..., description="Target model ID.")
    dataset_id: str = Field(..., description="Validation dataset ID.")
    evaluator_name: str = Field(default="default_classification")
    status: EvaluationStatus = Field(default=EvaluationStatus.CREATED)
    metrics: Optional[MetricResult] = Field(default=None)
    recommendation: Optional[PromotionRecommendation] = Field(default=None)
    report: Optional[EvaluationReport] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class EvaluationManager:
    """Thread-safe Evaluation Manager orchestrating evaluation, metrics, promotion rules, and reporting."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        engine: Optional[EvaluationEngine] = None,
        metrics_store: Optional[EvaluationMetricsStore] = None,
        promotion_engine: Optional[PromotionRuleEngine] = None,
        leaderboard: Optional[Leaderboard] = None,
        benchmark_mgr: Optional[BenchmarkManager] = None,
        report_store: Optional[EvaluationReportStore] = None,
        validation_mgr: Optional[ValidationManager] = None,
        max_evaluations: int = 500,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._max_evaluations = max_evaluations
        self._engine = engine or EvaluationEngine()
        self._metrics_store = metrics_store or EvaluationMetricsStore()
        self._promotion_engine = promotion_engine or PromotionRuleEngine()
        self._leaderboard = leaderboard or Leaderboard(event_bus=event_bus)
        self._benchmark_mgr = benchmark_mgr or BenchmarkManager(event_bus=event_bus, leaderboard=self._leaderboard)
        self._report_store = report_store or EvaluationReportStore()
        self._validation_mgr = validation_mgr or ValidationManager()

        # evaluation_id -> EvaluationRecord
        self._evaluations: Dict[str, EvaluationRecord] = {}

    def create_evaluation(
        self,
        model_id: str,
        dataset_id: str,
        evaluator_name: str = "default_classification",
    ) -> EvaluationRecord:
        """Create and register a new evaluation task."""
        with self._lock:
            if len(self._evaluations) >= self._max_evaluations:
                raise RuntimeError(f"EvaluationManager capacity exceeded: limit={self._max_evaluations}")

            record = EvaluationRecord(
                model_id=model_id,
                dataset_id=dataset_id,
                evaluator_name=evaluator_name,
                status=EvaluationStatus.CREATED,
            )
            self._evaluations[record.evaluation_id] = record

            logger.info("Created evaluation task '%s' for model '%s'", record.evaluation_id, model_id)

            if self._event_bus:
                self._event_bus.publish(
                    EvaluationCreated(
                        evaluation_id=record.evaluation_id,
                        model_id=model_id,
                        dataset_id=dataset_id,
                    )
                )
            return record

    def execute_evaluation(
        self,
        evaluation_id: str,
        predictions: Optional[List[Any]] = None,
        targets: Optional[List[Any]] = None,
        promotion_criteria: Optional[PromotionCriteria] = None,
        **kwargs: Any,
    ) -> EvaluationRecord:
        """Execute evaluation, compute metrics, evaluate promotion rules, update leaderboard and report."""
        with self._lock:
            record = self._evaluations.get(evaluation_id)
            if record is None:
                raise ValueError(f"Evaluation task '{evaluation_id}' not found")

            if record.status in (EvaluationStatus.COMPLETED, EvaluationStatus.CANCELLED):
                return record

            started_at = datetime.now(timezone.utc)
            running_record = EvaluationRecord(
                evaluation_id=record.evaluation_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                evaluator_name=record.evaluator_name,
                status=EvaluationStatus.RUNNING,
                created_at=record.created_at,
                started_at=started_at,
            )
            self._evaluations[evaluation_id] = running_record

            if self._event_bus:
                self._event_bus.publish(
                    EvaluationStarted(
                        evaluation_id=evaluation_id,
                        model_id=record.model_id,
                    )
                )

        try:
            # Step 1: Run Evaluation Engine
            metrics = self._engine.evaluate(
                evaluation_id=evaluation_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                predictions=predictions,
                targets=targets,
                evaluator_name=record.evaluator_name,
                **kwargs,
            )

            # Step 2: Store Metrics
            self._metrics_store.record_metrics(
                evaluation_id=evaluation_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                accuracy=metrics.accuracy,
                precision=metrics.precision,
                recall=metrics.recall,
                f1_score=metrics.f1_score,
                val_loss=metrics.val_loss,
                confusion_matrix=metrics.confusion_matrix,
                inference_latency_ms=metrics.inference_latency_ms,
                throughput=metrics.throughput,
                sample_count=metrics.sample_count,
            )

            # Step 3: Evaluate Promotion Rules
            recommendation = self._promotion_engine.evaluate_promotion(metrics, criteria=promotion_criteria)

            if self._event_bus:
                self._event_bus.publish(
                    PromotionEvaluated(
                        model_id=record.model_id,
                        is_eligible=recommendation.is_eligible,
                        reasons=recommendation.reasons,
                    )
                )

            # Step 4: Update Leaderboard
            all_metrics = self._metrics_store.list_all_metrics() if hasattr(self._metrics_store, "list_all_metrics") else [metrics]
            self._leaderboard.update_ranking("main_leaderboard", all_metrics, metric_name="accuracy")

            # Step 5: Generate Report
            report = self._report_store.create_report(
                model_id=record.model_id,
                evaluation_id=evaluation_id,
                metrics_summary=metrics,
                promotion_recommendation=recommendation,
            )

            with self._lock:
                latest = self._evaluations.get(evaluation_id)
                if latest and latest.status == EvaluationStatus.CANCELLED:
                    return latest

                completed_at = datetime.now(timezone.utc)
                completed_record = EvaluationRecord(
                    evaluation_id=evaluation_id,
                    model_id=record.model_id,
                    dataset_id=record.dataset_id,
                    evaluator_name=record.evaluator_name,
                    status=EvaluationStatus.COMPLETED,
                    metrics=metrics,
                    recommendation=recommendation,
                    report=report,
                    created_at=record.created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                self._evaluations[evaluation_id] = completed_record

                if self._event_bus:
                    self._event_bus.publish(
                        EvaluationCompleted(
                            evaluation_id=evaluation_id,
                            model_id=record.model_id,
                            accuracy=metrics.accuracy,
                            f1_score=metrics.f1_score,
                        )
                    )
                return completed_record

        except Exception as exc:  # noqa: BLE001
            with self._lock:
                latest = self._evaluations.get(evaluation_id)
                if latest and latest.status == EvaluationStatus.CANCELLED:
                    return latest

                completed_at = datetime.now(timezone.utc)
                failed_record = EvaluationRecord(
                    evaluation_id=evaluation_id,
                    model_id=record.model_id,
                    dataset_id=record.dataset_id,
                    evaluator_name=record.evaluator_name,
                    status=EvaluationStatus.FAILED,
                    error_message=str(exc),
                    created_at=record.created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                self._evaluations[evaluation_id] = failed_record

                if self._event_bus:
                    self._event_bus.publish(
                        EvaluationFailed(
                            evaluation_id=evaluation_id,
                            model_id=record.model_id,
                            error_message=str(exc),
                        )
                    )
                return failed_record

    def cancel_evaluation(self, evaluation_id: str, reason: str = "User cancelled") -> Optional[EvaluationRecord]:
        """Cancel an active evaluation task."""
        with self._lock:
            record = self._evaluations.get(evaluation_id)
            if record is None:
                return None

            if record.status in (EvaluationStatus.CANCELLED, EvaluationStatus.COMPLETED, EvaluationStatus.FAILED):
                return record

            cancelled_record = EvaluationRecord(
                evaluation_id=evaluation_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                evaluator_name=record.evaluator_name,
                status=EvaluationStatus.CANCELLED,
                error_message=f"Cancelled: {reason}",
                created_at=record.created_at,
                started_at=record.started_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._evaluations[evaluation_id] = cancelled_record

            if self._event_bus:
                self._event_bus.publish(
                    EvaluationCancelled(
                        evaluation_id=evaluation_id,
                        reason=reason,
                    )
                )
            return cancelled_record

    def retry_evaluation(self, evaluation_id: str, **kwargs: Any) -> Optional[EvaluationRecord]:
        """Retry a failed evaluation task."""
        with self._lock:
            record = self._evaluations.get(evaluation_id)
            if record is None or record.status != EvaluationStatus.FAILED:
                return None

            retry_record = EvaluationRecord(
                evaluation_id=evaluation_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                evaluator_name=record.evaluator_name,
                status=EvaluationStatus.CREATED,
                created_at=record.created_at,
            )
            self._evaluations[evaluation_id] = retry_record

        return self.execute_evaluation(evaluation_id, **kwargs)

    def get_evaluation(self, evaluation_id: str) -> Optional[EvaluationRecord]:
        """Retrieve evaluation task by ID."""
        with self._lock:
            return self._evaluations.get(evaluation_id)

    def list_evaluations(self, status: Optional[EvaluationStatus] = None) -> List[EvaluationRecord]:
        """List evaluation tasks, optionally filtered by status."""
        with self._lock:
            records = list(self._evaluations.values())
            if status:
                records = [r for r in records if r.status == status]
            return records

    def count(self) -> int:
        """Return total count of registered evaluations."""
        with self._lock:
            return len(self._evaluations)

    def clear(self) -> None:
        """Clear all evaluations and sub-component stores."""
        with self._lock:
            self._evaluations.clear()
            self._metrics_store.clear()
            self._leaderboard.clear()
            self._benchmark_mgr.clear()
            self._report_store.clear()
            self._validation_mgr.clear()
