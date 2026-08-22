"""Experiment Tracker monitoring hyper-parameters, metrics, and artifact records.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from research_platform.data_platform.models import ExperimentArtifact, ExperimentRun


class ExperimentTracker:
    """Manages experiment runs, tracking metrics, configurations, and artifacts paths."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, ExperimentRun] = {}
        self._artifacts: Dict[str, List[ExperimentArtifact]] = {}

    def start_run(
        self,
        run_id: str,
        experiment_id: str,
        parameters: Dict[str, Any]
    ) -> ExperimentRun:
        """Create and initialize a new ExperimentRun."""
        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            parameters=parameters,
            metrics={},
            artifacts=[],
            status="RUNNING",
            timestamp=datetime.now(timezone.utc)
        )
        with self._lock:
            self._runs[run_id] = run
        return run

    def log_metrics(self, run_id: str, metrics: Dict[str, float]) -> None:
        """Log or update metrics for a running experiment."""
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Experiment run '{run_id}' not found.")
            run = self._runs[run_id]
            updated_metrics = run.metrics.copy()
            updated_metrics.update(metrics)
            
            self._runs[run_id] = ExperimentRun(
                run_id=run.run_id,
                experiment_id=run.experiment_id,
                parameters=run.parameters,
                metrics=updated_metrics,
                artifacts=run.artifacts,
                status=run.status,
                timestamp=run.timestamp
            )

    def log_artifact(
        self,
        run_id: str,
        artifact_id: str,
        name: str,
        file_path: str,
        category: str
    ) -> ExperimentArtifact:
        """Log an output artifact file generated during the run."""
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        art = ExperimentArtifact(
            artifact_id=artifact_id,
            run_id=run_id,
            name=name,
            file_path=file_path,
            category=category,
            size_bytes=size
        )
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Experiment run '{run_id}' not found.")
            if run_id not in self._artifacts:
                self._artifacts[run_id] = []
            self._artifacts[run_id].append(art)
            
            # Update artifacts list in run
            run = self._runs[run_id]
            updated_arts = run.artifacts.copy()
            updated_arts.append(artifact_id)
            
            self._runs[run_id] = ExperimentRun(
                run_id=run.run_id,
                experiment_id=run.experiment_id,
                parameters=run.parameters,
                metrics=run.metrics,
                artifacts=updated_arts,
                status=run.status,
                timestamp=run.timestamp
            )
        return art

    def complete_run(self, run_id: str, status: str = "COMPLETED") -> None:
        """Transition running experiment status to completed or failed."""
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"Experiment run '{run_id}' not found.")
            run = self._runs[run_id]
            self._runs[run_id] = ExperimentRun(
                run_id=run.run_id,
                experiment_id=run.experiment_id,
                parameters=run.parameters,
                metrics=run.metrics,
                artifacts=run.artifacts,
                status=status,
                timestamp=run.timestamp
            )

    def get_run(self, run_id: str) -> Optional[ExperimentRun]:
        with self._lock:
            return self._runs.get(run_id)
            
    def get_artifacts(self, run_id: str) -> List[ExperimentArtifact]:
        with self._lock:
            return list(self._artifacts.get(run_id, []))
