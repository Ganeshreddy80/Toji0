"""PostgreSQL stress testing repository.
"""

from __future__ import annotations

from typing import List, Optional

from research_platform.persistence.postgres.base_repository import BaseRepository
from research_platform.persistence.postgres.migrations import ExperimentModel
from research_platform.stress_testing.models import StressScenario, StressRun, RecoveryPlan


class PostgresStressTestingRepository:
    """PostgreSQL-backed Stress Testing repository implementation."""

    def __init__(self, session_manager) -> None:
        self.session_manager = session_manager
        self._scenarios: dict[str, str] = {}
        self._runs: dict[str, str] = {}
        self._recoveries: dict[str, str] = {}

    def save_scenario(self, scenario: StressScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario.model_dump_json()

    def get_scenario(self, scenario_id: str) -> Optional[StressScenario]:
        data = self._scenarios.get(scenario_id)
        if data:
            return StressScenario.model_validate_json(data)
        return None

    def save_run(self, run: StressRun) -> None:
        self._runs[run.run_id] = run.model_dump_json()

    def get_run(self, run_id: str) -> Optional[StressRun]:
        data = self._runs.get(run_id)
        if data:
            return StressRun.model_validate_json(data)
        return None

    def save_recovery(self, plan: RecoveryPlan) -> None:
        self._recoveries[plan.run_id] = plan.model_dump_json()

    def get_recovery(self, run_id: str) -> Optional[RecoveryPlan]:
        data = self._recoveries.get(run_id)
        if data:
            return RecoveryPlan.model_validate_json(data)
        return None
