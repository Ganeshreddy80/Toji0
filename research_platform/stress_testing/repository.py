"""Stress testing repository with PostgreSQL delegation and memory fallbacks.
"""

from __future__ import annotations

import threading
from typing import Dict, Optional
from research_platform.stress_testing.interfaces import IStressTestingRepository
from research_platform.stress_testing.models import StressScenario, StressRun, RecoveryPlan
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.persistence.repositories.stress_repository import PostgresStressTestingRepository


class StressTestingRepository(IStressTestingRepository):
    """Memory-backed repository with PostgreSQL delegation capabilities."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._scenarios: Dict[str, StressScenario] = {}
        self._runs: Dict[str, StressRun] = {}
        self._recoveries: Dict[str, RecoveryPlan] = {}

    def _get_pg_repo(self) -> Optional[PostgresStressTestingRepository]:
        registry = ServiceRegistry()
        db = registry.get_service("Database")
        if db:
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            session_manager = DatabaseSessionManager(db)
            return PostgresStressTestingRepository(session_manager)
        return None

    def save_scenario(self, scenario: StressScenario) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_scenario(scenario)
            
        with self._lock:
            self._scenarios[scenario.scenario_id] = scenario

    def get_scenario(self, scenario_id: str) -> Optional[StressScenario]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_scenario(scenario_id)
            
        with self._lock:
            return self._scenarios.get(scenario_id)

    def save_run(self, run: StressRun) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_run(run)
            
        with self._lock:
            self._runs[run.run_id] = run

    def get_run(self, run_id: str) -> Optional[StressRun]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_run(run_id)
            
        with self._lock:
            return self._runs.get(run_id)

    def save_recovery(self, plan: RecoveryPlan) -> None:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            pg_repo.save_recovery(plan)
            
        with self._lock:
            self._recoveries[plan.run_id] = plan

    def get_recovery(self, run_id: str) -> Optional[RecoveryPlan]:
        pg_repo = self._get_pg_repo()
        if pg_repo:
            return pg_repo.get_recovery(run_id)
            
        with self._lock:
            return self._recoveries.get(run_id)
