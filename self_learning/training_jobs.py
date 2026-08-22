"""Thread-safe Training Job Lifecycle Manager for the Self Learning Engine (Sprint 11A)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from self_learning.metadata import TrainingMetadata
from self_learning.models.learning_models import TrainingJobRecord, TrainingJobStatus
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Training Events
# ---------------------------------------------------------------------------

class TrainingStarted(BaseModel):
    """Event published when a training job transitions to RUNNING."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="TrainingStarted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    job_id: str
    model_id: str
    dataset_id: str

    model_config = ConfigDict(frozen=True)


class TrainingCompleted(BaseModel):
    """Event published when a training job successfully completes."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="TrainingCompleted")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    job_id: str
    model_id: str
    result_metrics: Dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class TrainingFailed(BaseModel):
    """Event published when a training job fails."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="TrainingFailed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    job_id: str
    model_id: str
    error_message: str

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Training Job Manager
# ---------------------------------------------------------------------------

class TrainingJobManager:
    """Thread-safe training job lifecycle manager.

    Supports full job lifecycle: PENDING → RUNNING → COMPLETED/FAILED/CANCELLED.
    All job records are immutable Pydantic V2 models replaced on each state transition.
    """

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        max_jobs: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._jobs: Dict[str, TrainingJobRecord] = {}
        self._metadata: Dict[str, TrainingMetadata] = {}
        self._max_jobs = max_jobs

    def create_job(
        self,
        model_id: str,
        dataset_id: str,
        description: str = "",
        hyperparameters: Optional[Dict[str, Any]] = None,
    ) -> TrainingJobRecord:
        """Create and register a new training job in PENDING state."""
        with self._lock:
            record = TrainingJobRecord(
                model_id=model_id,
                dataset_id=dataset_id,
                status=TrainingJobStatus.PENDING,
                description=description,
                hyperparameters=hyperparameters or {},
            )
            self._jobs[record.job_id] = record
            logger.info("Created training job '%s' for model '%s'", record.job_id, model_id)
            return record

    def start_job(self, job_id: str) -> Optional[TrainingJobRecord]:
        """Transition a PENDING job to RUNNING and publish TrainingStarted event."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record.status != TrainingJobStatus.PENDING:
                return None

            updated = TrainingJobRecord(
                job_id=record.job_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                status=TrainingJobStatus.RUNNING,
                description=record.description,
                hyperparameters=record.hyperparameters,
                created_at=record.created_at,
                started_at=datetime.now(timezone.utc),
            )
            self._jobs[job_id] = updated

            if self._event_bus:
                self._event_bus.publish(
                    TrainingStarted(
                        job_id=job_id,
                        model_id=record.model_id,
                        dataset_id=record.dataset_id,
                    )
                )
            logger.info("Training job '%s' STARTED", job_id)
            return updated

    def complete_job(
        self,
        job_id: str,
        result_metrics: Optional[Dict[str, float]] = None,
    ) -> Optional[TrainingJobRecord]:
        """Transition a RUNNING job to COMPLETED and record metrics."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record.status != TrainingJobStatus.RUNNING:
                return None

            completed_at = datetime.now(timezone.utc)
            metrics = result_metrics or {}
            duration = (
                (completed_at - record.started_at).total_seconds()
                if record.started_at else None
            )
            updated = TrainingJobRecord(
                job_id=record.job_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                status=TrainingJobStatus.COMPLETED,
                description=record.description,
                hyperparameters=record.hyperparameters,
                created_at=record.created_at,
                started_at=record.started_at,
                completed_at=completed_at,
                result_metrics=metrics,
            )
            self._jobs[job_id] = updated

            # Persist training metadata
            self._metadata[job_id] = TrainingMetadata(
                job_id=job_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                hyperparameters=record.hyperparameters,
                result_metrics=metrics,
                duration_seconds=duration,
            )

            if self._event_bus:
                self._event_bus.publish(
                    TrainingCompleted(
                        job_id=job_id,
                        model_id=record.model_id,
                        result_metrics=metrics,
                    )
                )
            logger.info("Training job '%s' COMPLETED with metrics: %s", job_id, metrics)
            return updated

    def fail_job(self, job_id: str, error_message: str) -> Optional[TrainingJobRecord]:
        """Transition a RUNNING job to FAILED."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record.status != TrainingJobStatus.RUNNING:
                return None

            updated = TrainingJobRecord(
                job_id=record.job_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                status=TrainingJobStatus.FAILED,
                description=record.description,
                hyperparameters=record.hyperparameters,
                created_at=record.created_at,
                started_at=record.started_at,
                completed_at=datetime.now(timezone.utc),
                error_message=error_message,
            )
            self._jobs[job_id] = updated

            if self._event_bus:
                self._event_bus.publish(
                    TrainingFailed(
                        job_id=job_id,
                        model_id=record.model_id,
                        error_message=error_message,
                    )
                )
            logger.warning("Training job '%s' FAILED: %s", job_id, error_message)
            return updated

    def cancel_job(self, job_id: str) -> Optional[TrainingJobRecord]:
        """Cancel a PENDING or RUNNING job."""
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None or record.status not in (
                TrainingJobStatus.PENDING, TrainingJobStatus.RUNNING
            ):
                return None

            updated = TrainingJobRecord(
                job_id=record.job_id,
                model_id=record.model_id,
                dataset_id=record.dataset_id,
                status=TrainingJobStatus.CANCELLED,
                description=record.description,
                hyperparameters=record.hyperparameters,
                created_at=record.created_at,
                started_at=record.started_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._jobs[job_id] = updated
            logger.info("Training job '%s' CANCELLED", job_id)
            return updated

    def get_job(self, job_id: str) -> Optional[TrainingJobRecord]:
        """Get training job record by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_metadata(self, job_id: str) -> Optional[TrainingMetadata]:
        """Get training metadata for a completed job."""
        with self._lock:
            return self._metadata.get(job_id)

    def list_jobs(
        self,
        model_id: Optional[str] = None,
        status: Optional[TrainingJobStatus] = None,
    ) -> List[TrainingJobRecord]:
        """List training jobs with optional filters."""
        with self._lock:
            records = list(self._jobs.values())
            if model_id:
                records = [r for r in records if r.model_id == model_id]
            if status:
                records = [r for r in records if r.status == status]
            return records

    def count(self) -> int:
        with self._lock:
            return len(self._jobs)

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
            self._metadata.clear()
