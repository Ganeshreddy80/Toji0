"""Manager service for versioning, storing, and running research experiments."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from research.experiments.models import (
    ExperimentResult,
    ExperimentRun,
    ExperimentStatus,
    ResearchExperiment,
)


class ExperimentManager:
    """Manages active research configurations, logs runs, and archives quant experiments."""

    def __init__(self) -> None:
        # In-memory backing stores for platform MVP
        self._experiments: dict[str, ResearchExperiment] = {}
        self._runs: dict[str, ExperimentRun] = {}
        self._results: dict[str, ExperimentResult] = {}

    def create_experiment(
        self,
        name: str,
        description: str,
        dataset_ref: str,
        asset_universe: list[str],
        version: str = "1.0.0",
        tags: list[str] | None = None,
        dependencies: list[str] | None = None,
        feature_refs: list[str] | None = None,
        market_regime: str | None = None,
    ) -> ResearchExperiment:
        """Create a new experiment configuration."""
        exp_id = str(uuid.uuid4())
        experiment = ResearchExperiment(
            experiment_id=exp_id,
            name=name,
            description=description,
            dataset_ref=dataset_ref,
            asset_universe=asset_universe,
            version=version,
            tags=tags or [],
            dependencies=dependencies or [],
            feature_refs=feature_refs or [],
            market_regime=market_regime,
            created_at=datetime.now(timezone.utc),
        )
        self._experiments[exp_id] = experiment
        return experiment

    def get_experiment(self, experiment_id: str) -> ResearchExperiment | None:
        """Retrieve an experiment by its unique ID."""
        return self._experiments.get(experiment_id)

    def start_run(self, experiment_id: str, notes: str | None = None) -> ExperimentRun:
        """Initialize and log a new run for a specific experiment."""
        if experiment_id not in self._experiments:
            raise KeyError(f"Experiment '{experiment_id}' does not exist.")

        run_id = str(uuid.uuid4())
        run = ExperimentRun(
            run_id=run_id,
            experiment_id=experiment_id,
            status=ExperimentStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            metrics={},
            logs=["Run started"],
            notes=notes,
        )
        self._runs[run_id] = run
        return run

    def complete_run(
        self,
        run_id: str,
        status: ExperimentStatus,
        metrics: dict[str, float],
        logs: list[str],
        notes: str | None = None,
        conclusion: str | None = None,
    ) -> tuple[ExperimentRun, ExperimentResult | None]:
        """Mark a run as complete and store its corresponding results if successful."""
        if run_id not in self._runs:
            raise KeyError(f"Run '{run_id}' not found.")

        old_run = self._runs[run_id]

        new_run = ExperimentRun(
            run_id=old_run.run_id,
            experiment_id=old_run.experiment_id,
            status=status,
            started_at=old_run.started_at,
            completed_at=datetime.now(timezone.utc),
            metrics=metrics,
            logs=old_run.logs + logs,
            notes=notes or old_run.notes,
        )
        self._runs[run_id] = new_run

        result = None
        if status == ExperimentStatus.SUCCESS:
            res_id = str(uuid.uuid4())
            result = ExperimentResult(
                result_id=res_id,
                run_id=run_id,
                metrics=metrics,
                plots={},
                conclusion=conclusion or "Experiment run completed successfully.",
            )
            self._results[res_id] = result

        return new_run, result

    def get_run(self, run_id: str) -> ExperimentRun | None:
        """Retrieve a specific run by ID."""
        return self._runs.get(run_id)

    def get_result_for_run(self, run_id: str) -> ExperimentResult | None:
        """Retrieve the result associated with a run."""
        for result in self._results.values():
            if result.run_id == run_id:
                return result
        return None

    def compare_runs(self, run_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Compare metrics across different experiment runs."""
        comparison: dict[str, dict[str, Any]] = {}
        for r_id in run_ids:
            run = self.get_run(r_id)
            if run:
                comparison[r_id] = {
                    "experiment_id": run.experiment_id,
                    "status": run.status.value,
                    "metrics": run.metrics,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                }
        return comparison
