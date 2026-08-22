"""Experiment manager configuration repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.experiment_manager.interfaces import IExperimentRepository
from research_platform.experiment_manager.models import Experiment
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.experiment_repository import PostgresExperimentRepository


class ExperimentRepository(IExperimentRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._experiments: Dict[str, Experiment] = {}

    def _get_pg_repo(self) -> Optional[PostgresExperimentRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresExperimentRepository(session_manager)
        return None

    def save_experiment(self, experiment: Experiment) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_experiment(experiment)
            
        with self._lock:
            self._experiments[experiment.experiment_id] = experiment

    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_experiment(experiment_id)
            
        with self._lock:
            return self._experiments.get(experiment_id)

    def list_experiments(self) -> List[Experiment]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.list_experiments()
            
        with self._lock:
            return list(self._experiments.values())
