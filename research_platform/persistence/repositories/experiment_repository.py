"""PostgreSQL experiment repository.
"""

from __future__ import annotations

from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import ExperimentModel
from research_platform.experiment_manager.models import Experiment


class PostgresExperimentRepository(BaseRepository):
    """PostgreSQL-backed Experiment repository implementation."""

    def __init__(self, session_manager) -> None:
        super().__init__(session_manager, ExperimentModel)

    def save_experiment(self, experiment: Experiment) -> None:
        model = self.get(experiment.experiment_id)
        serialized_data = {
            "description": experiment.description,
            "reproducibility": experiment.reproducibility.model_dump(),
            "results": experiment.results
        }
        if model:
            updates = {
                "name": experiment.name,
                "status": experiment.status,
                "metrics": serialized_data
            }
            self.update(experiment.experiment_id, updates)
        else:
            new_model = ExperimentModel(
                experiment_id=experiment.experiment_id,
                name=experiment.name,
                status=experiment.status,
                metrics=serialized_data
            )
            self.create(new_model)

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        model = self.get(experiment_id)
        if model and model.metrics:
            from research_platform.experiment_manager.models import ReproducibilitySnapshot
            return Experiment(
                experiment_id=model.experiment_id,
                name=model.name,
                status=model.status,
                description=model.metrics.get("description", ""),
                reproducibility=ReproducibilitySnapshot(**model.metrics["reproducibility"]),
                results=model.metrics.get("results", {})
            )
        return None

    def list_experiments(self) -> List[Experiment]:
        models = self.list_all()
        results = []
        from research_platform.experiment_manager.models import ReproducibilitySnapshot
        for m in models:
            if m.metrics:
                results.append(
                    Experiment(
                        experiment_id=m.experiment_id,
                        name=m.name,
                        status=m.status,
                        description=m.metrics.get("description", ""),
                        reproducibility=ReproducibilitySnapshot(**m.metrics["reproducibility"]),
                        results=m.metrics.get("results", {})
                    )
                )
        return results
