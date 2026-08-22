"""Experiment engine managing creation, cloning, archiving of quant runs.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from research_platform.experiment_manager.models import Experiment, ReproducibilitySnapshot


class ExperimentEngine:
    """Creates versioned experiment records."""

    def initiate_experiment(
        self,
        experiment_id: str,
        name: str,
        description: str,
        tags: List[str],
        group_id: str,
        reproducibility: ReproducibilitySnapshot
    ) -> Experiment:
        if not experiment_id or not name:
            raise ValueError("Experiment ID and Name must not be blank.")

        return Experiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            tags=tags,
            group_id=group_id,
            reproducibility=reproducibility
        )

    def clone_experiment(self, source: Experiment, new_id: str) -> Experiment:
        return source.model_copy(update={
            "experiment_id": new_id,
            "name": f"Clone of {source.name}"
        })
