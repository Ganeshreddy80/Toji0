"""Thread-safe Training Executor for the Self Learning Engine (Sprint 11B)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

from self_learning.artifact_manager import ArtifactManager
from self_learning.checkpoint_manager import CheckpointManager
from self_learning.metrics_collector import MetricsCollector
from self_learning.pipeline_state import PipelineConfig
from self_learning.resource_allocator import ResourceAllocator

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Immutable summary of an execution attempt."""

    def __init__(
        self,
        success: bool,
        metrics: Dict[str, float],
        error_message: Optional[str] = None,
        retries_used: int = 0,
        stage: str = "COMPLETED",
    ) -> None:
        self.success = success
        self.metrics = metrics
        self.error_message = error_message
        self.retries_used = retries_used
        self.stage = stage


class TrainingExecutor:
    """Thread-safe training and evaluation executor with timeout and retry policies.

    Executes data preparation, model training stage, and evaluation stage.
    Manages resource reservation, checkpointing, artifact registration, and metrics collection.
    Advisory only — no broker or trading interaction.
    """

    def __init__(
        self,
        resource_allocator: Optional[ResourceAllocator] = None,
        checkpoint_manager: Optional[CheckpointManager] = None,
        artifact_manager: Optional[ArtifactManager] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._allocator = resource_allocator or ResourceAllocator()
        self._checkpoint_mgr = checkpoint_manager or CheckpointManager()
        self._artifact_mgr = artifact_manager or ArtifactManager()
        self._metrics_collector = metrics_collector or MetricsCollector()

    def execute_stage(
        self,
        config: PipelineConfig,
        custom_trainer: Optional[Callable[[PipelineConfig], Dict[str, float]]] = None,
    ) -> ExecutionResult:
        """Execute full training lifecycle with retry and timeout handling."""
        start_time = time.perf_counter()

        # Step 1: Reserve Resources
        reservation = self._allocator.reserve_resources(
            pipeline_id=config.pipeline_id,
            cpu_cores=config.cpu_cores,
            memory_mb=config.memory_mb,
        )
        if reservation is None:
            return ExecutionResult(
                success=False,
                metrics={},
                error_message="Resource reservation failed — insufficient capacity",
                stage="RESOURCE_ALLOCATION",
            )

        try:
            attempts = 0
            max_attempts = max(1, config.max_retries + 1)
            last_error: Optional[str] = None

            while attempts < max_attempts:
                attempts += 1
                try:
                    # Check timeout before running attempt
                    elapsed = time.perf_counter() - start_time
                    if elapsed > config.timeout_seconds:
                        raise TimeoutError(f"Pipeline execution timed out after {elapsed:.2f}s (limit={config.timeout_seconds}s)")

                    # Step 2: Model Training Stage
                    metrics = self._run_training(config, custom_trainer)

                    # Step 3: Evaluation Stage
                    eval_metrics = self._run_evaluation(config, metrics)
                    combined_metrics = {**metrics, **eval_metrics}

                    elapsed_total = time.perf_counter() - start_time
                    combined_metrics["duration_seconds"] = round(elapsed_total, 4)

                    # Check timeout after stages
                    if elapsed_total > config.timeout_seconds:
                        raise TimeoutError(f"Pipeline execution timed out after {elapsed_total:.2f}s (limit={config.timeout_seconds}s)")

                    # Step 4: Checkpointing & Artifact Registration
                    self._checkpoint_mgr.save_checkpoint(
                        pipeline_id=config.pipeline_id,
                        epoch=10,
                        step=1000,
                        state_dict={"model_id": config.model_id, "status": "trained"},
                    )
                    self._artifact_mgr.register_artifact(
                        name=f"{config.name}_weights",
                        pipeline_id=config.pipeline_id,
                        artifact_type="model_weights",
                        version="1.0.0",
                        metadata=combined_metrics,
                    )

                    # Step 5: Metrics Collection
                    self._metrics_collector.record_metrics(
                        pipeline_id=config.pipeline_id,
                        duration_seconds=elapsed_total,
                        accuracy=combined_metrics.get("accuracy"),
                        loss=combined_metrics.get("loss"),
                        validation_metrics={"val_loss": combined_metrics.get("val_loss", 0.0)},
                        throughput=combined_metrics.get("throughput", 100.0),
                    )

                    logger.info("Pipeline '%s' execution succeeded (attempts=%d)", config.pipeline_id, attempts)
                    return ExecutionResult(
                        success=True,
                        metrics=combined_metrics,
                        retries_used=attempts - 1,
                        stage="COMPLETED",
                    )

                except TimeoutError as te:
                    last_error = str(te)
                    logger.warning("Pipeline '%s' attempt %d timed out: %s", config.pipeline_id, attempts, te)
                    break  # Timeout is terminal for this run
                except Exception as exc:  # noqa: BLE001
                    last_error = f"Attempt {attempts} error: {exc}"
                    logger.warning("Pipeline '%s' attempt %d failed: %s", config.pipeline_id, attempts, exc)
                    if attempts >= max_attempts:
                        break

            return ExecutionResult(
                success=False,
                metrics={},
                error_message=last_error or "Pipeline execution failed after retries",
                retries_used=attempts - 1,
                stage="FAILED",
            )

        finally:
            self._allocator.release_resources(config.pipeline_id)

    def _run_training(
        self,
        config: PipelineConfig,
        custom_trainer: Optional[Callable[[PipelineConfig], Dict[str, float]]] = None,
    ) -> Dict[str, float]:
        """Execute simulated training stage."""
        if custom_trainer:
            return custom_trainer(config)

        # Simulated default training metrics
        return {
            "loss": 0.15,
            "accuracy": 0.94,
            "throughput": 250.0,
        }

    def _run_evaluation(self, config: PipelineConfig, train_metrics: Dict[str, float]) -> Dict[str, float]:
        """Execute simulated evaluation stage."""
        val_loss = train_metrics.get("loss", 0.2) + 0.02
        val_acc = max(0.0, train_metrics.get("accuracy", 0.9) - 0.02)
        return {
            "val_loss": round(val_loss, 4),
            "val_accuracy": round(val_acc, 4),
        }
