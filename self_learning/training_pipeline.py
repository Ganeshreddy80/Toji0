"""Thread-safe Training Pipeline Manager for the Self Learning Engine (Sprint 11B)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from self_learning.artifact_manager import ArtifactManager
from self_learning.checkpoint_manager import CheckpointManager
from self_learning.metrics_collector import MetricsCollector
from self_learning.pipeline_state import PipelineConfig, PipelineRecord, PipelineStatus
from self_learning.resource_allocator import ResourceAllocator
from self_learning.training_events import (
    PipelineCancelled,
    PipelineCompleted,
    PipelineCreated,
    PipelineFailed,
    PipelineQueued,
    PipelineStarted,
)
from self_learning.training_executor import ExecutionResult, TrainingExecutor
from self_learning.training_scheduler import TrainingScheduler
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class TrainingPipelineManager:
    """Thread-safe Training Pipeline Manager orchestrating the full ML training lifecycle.

    Integrates priority scheduling, execution, resource allocation, checkpointing,
    artifact management, and event publication.
    Enforces advisory-only execution boundaries — no live trading coupling.
    """

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        scheduler: Optional[TrainingScheduler] = None,
        executor: Optional[TrainingExecutor] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        resource_allocator: Optional[ResourceAllocator] = None,
        max_pipelines: int = 500,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._max_pipelines = max_pipelines
        self._scheduler = scheduler or TrainingScheduler()
        self._allocator = resource_allocator or ResourceAllocator()
        self._checkpoint_mgr = checkpoint_manager or CheckpointManager()
        self._artifact_mgr = artifact_manager or ArtifactManager()
        self._metrics_collector = metrics_collector or MetricsCollector()
        self._executor = executor or TrainingExecutor(
            resource_allocator=self._allocator,
            checkpoint_manager=self._checkpoint_mgr,
            artifact_manager=self._artifact_mgr,
            metrics_collector=self._metrics_collector,
        )

        # pipeline_id -> PipelineRecord
        self._pipelines: Dict[str, PipelineRecord] = {}

    def create_pipeline(
        self,
        name: str,
        model_id: str,
        dataset_id: str,
        priority: int = 0,
        max_retries: int = 3,
        timeout_seconds: float = 60.0,
        cpu_cores: float = 2.0,
        memory_mb: float = 4096.0,
        hyperparameters: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PipelineRecord:
        """Create and register a new training pipeline in CREATED state."""
        with self._lock:
            if len(self._pipelines) >= self._max_pipelines:
                raise RuntimeError(
                    f"TrainingPipelineManager capacity exceeded: limit={self._max_pipelines}"
                )

            config = PipelineConfig(
                name=name,
                model_id=model_id,
                dataset_id=dataset_id,
                priority=priority,
                max_retries=max_retries,
                timeout_seconds=timeout_seconds,
                cpu_cores=cpu_cores,
                memory_mb=memory_mb,
                hyperparameters=hyperparameters or {},
                metadata=metadata or {},
            )
            record = PipelineRecord(
                pipeline_id=config.pipeline_id,
                config=config,
                status=PipelineStatus.CREATED,
            )
            self._pipelines[record.pipeline_id] = record

            logger.info("Created pipeline '%s' (name='%s')", record.pipeline_id, name)

            if self._event_bus:
                self._event_bus.publish(
                    PipelineCreated(
                        pipeline_id=record.pipeline_id,
                        pipeline_name=name,
                        model_id=model_id,
                        dataset_id=dataset_id,
                    )
                )
            return record

    def queue_pipeline(self, pipeline_id: str) -> Optional[PipelineRecord]:
        """Place a CREATED or RETRYING pipeline into the priority scheduler queue."""
        with self._lock:
            record = self._pipelines.get(pipeline_id)
            if record is None or record.status not in (PipelineStatus.CREATED, PipelineStatus.RETRYING):
                logger.warning("queue_pipeline: pipeline '%s' not found or invalid status", pipeline_id)
                return None

            queued = self._scheduler.queue_job(record.config)
            if not queued:
                return None

            updated = PipelineRecord(
                pipeline_id=record.pipeline_id,
                config=record.config,
                status=PipelineStatus.QUEUED,
                current_retry=record.current_retry,
                created_at=record.created_at,
            )
            self._pipelines[pipeline_id] = updated

            if self._event_bus:
                self._event_bus.publish(
                    PipelineQueued(
                        pipeline_id=pipeline_id,
                        priority=record.config.priority,
                    )
                )
            return updated

    def execute_pipeline(
        self,
        pipeline_id: str,
        custom_trainer: Optional[Any] = None,
    ) -> PipelineRecord:
        """Execute a pipeline. If queued, pops from scheduler; transitions to RUNNING and completes/fails."""
        with self._lock:
            record = self._pipelines.get(pipeline_id)
            if record is None:
                raise ValueError(f"Pipeline '{pipeline_id}' not found")

            if record.status in (PipelineStatus.COMPLETED, PipelineStatus.CANCELLED):
                return record

            # Transition to RUNNING
            started_at = datetime.now(timezone.utc)
            running_record = PipelineRecord(
                pipeline_id=record.pipeline_id,
                config=record.config,
                status=PipelineStatus.RUNNING,
                current_retry=record.current_retry,
                created_at=record.created_at,
                started_at=started_at,
            )
            self._pipelines[pipeline_id] = running_record

            if self._event_bus:
                self._event_bus.publish(
                    PipelineStarted(
                        pipeline_id=pipeline_id,
                        model_id=record.config.model_id,
                    )
                )

        # Execute outside pipeline lock to allow concurrent queries
        res: ExecutionResult = self._executor.execute_stage(record.config, custom_trainer=custom_trainer)

        with self._lock:
            latest = self._pipelines.get(pipeline_id)
            if latest and latest.status == PipelineStatus.CANCELLED:
                return latest

            completed_at = datetime.now(timezone.utc)
            if res.success:
                final_record = PipelineRecord(
                    pipeline_id=pipeline_id,
                    config=record.config,
                    status=PipelineStatus.COMPLETED,
                    current_retry=record.current_retry + res.retries_used,
                    created_at=record.created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                self._pipelines[pipeline_id] = final_record

                if self._event_bus:
                    self._event_bus.publish(
                        PipelineCompleted(
                            pipeline_id=pipeline_id,
                            metrics=res.metrics,
                        )
                    )
                return final_record

            # Handle Failure
            failed_record = PipelineRecord(
                pipeline_id=pipeline_id,
                config=record.config,
                status=PipelineStatus.FAILED,
                current_retry=record.current_retry + res.retries_used,
                error_message=res.error_message,
                created_at=record.created_at,
                started_at=started_at,
                completed_at=completed_at,
            )
            self._pipelines[pipeline_id] = failed_record

            if self._event_bus:
                self._event_bus.publish(
                    PipelineFailed(
                        pipeline_id=pipeline_id,
                        error_message=res.error_message or "Unknown failure",
                    )
                )
            return failed_record

    def cancel_pipeline(self, pipeline_id: str, reason: str = "User cancelled") -> Optional[PipelineRecord]:
        """Cancel a created, queued, or running pipeline."""
        with self._lock:
            record = self._pipelines.get(pipeline_id)
            if record is None:
                return None

            if record.status in (PipelineStatus.CANCELLED, PipelineStatus.COMPLETED, PipelineStatus.FAILED):
                return record

            # Remove from scheduler if queued
            self._scheduler.cancel_queued_job(pipeline_id)
            # Release resources if running
            self._allocator.release_resources(pipeline_id)

            cancelled_record = PipelineRecord(
                pipeline_id=pipeline_id,
                config=record.config,
                status=PipelineStatus.CANCELLED,
                current_retry=record.current_retry,
                error_message=f"Cancelled: {reason}",
                created_at=record.created_at,
                started_at=record.started_at,
                completed_at=datetime.now(timezone.utc),
            )
            self._pipelines[pipeline_id] = cancelled_record

            if self._event_bus:
                self._event_bus.publish(
                    PipelineCancelled(
                        pipeline_id=pipeline_id,
                        reason=reason,
                    )
                )
            return cancelled_record

    def retry_pipeline(self, pipeline_id: str) -> Optional[PipelineRecord]:
        """Transition a FAILED pipeline to RETRYING and re-execute it."""
        with self._lock:
            record = self._pipelines.get(pipeline_id)
            if record is None or record.status != PipelineStatus.FAILED:
                logger.warning("retry_pipeline: pipeline '%s' is not in FAILED state", pipeline_id)
                return None

            if record.current_retry >= record.config.max_retries:
                logger.warning("retry_pipeline: max retries reached (%d/%d)", record.current_retry, record.config.max_retries)
                return record

            retry_record = PipelineRecord(
                pipeline_id=pipeline_id,
                config=record.config,
                status=PipelineStatus.RETRYING,
                current_retry=record.current_retry + 1,
                created_at=record.created_at,
            )
            self._pipelines[pipeline_id] = retry_record

        # Execute retry
        return self.execute_pipeline(pipeline_id)

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineRecord]:
        """Retrieve a pipeline record by ID."""
        with self._lock:
            return self._pipelines.get(pipeline_id)

    def list_pipelines(self, status: Optional[PipelineStatus] = None) -> List[PipelineRecord]:
        """List all pipeline records, optionally filtered by status."""
        with self._lock:
            records = list(self._pipelines.values())
            if status:
                records = [r for r in records if r.status == status]
            return records

    def count(self) -> int:
        """Return count of registered pipelines."""
        with self._lock:
            return len(self._pipelines)

    def clear(self) -> None:
        """Clear all pipelines and sub-components."""
        with self._lock:
            self._pipelines.clear()
            self._scheduler.clear()
            self._allocator.clear()
            self._checkpoint_mgr.clear()
            self._artifact_mgr.clear()
            self._metrics_collector.clear()
