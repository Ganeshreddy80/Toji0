"""Abstract contracts for the Stress Testing Engine.
"""

from __future__ import annotations

import abc
from typing import Optional
from research_platform.stress_testing.models import StressScenario, StressRun, RecoveryPlan


class IStressTestingRepository(abc.ABC):
    """Abstract contract for persisting stress scenarios and runs."""

    @abc.abstractmethod
    def save_scenario(self, scenario: StressScenario) -> None:
        """Persist stress scenario configuration."""

    @abc.abstractmethod
    def get_scenario(self, scenario_id: str) -> Optional[StressScenario]:
        """Retrieve stress scenario configuration by ID."""

    @abc.abstractmethod
    def save_run(self, run: StressRun) -> None:
        """Persist stress execution run details."""

    @abc.abstractmethod
    def get_run(self, run_id: str) -> Optional[StressRun]:
        """Retrieve stress execution run details by ID."""

    @abc.abstractmethod
    def save_recovery(self, plan: RecoveryPlan) -> None:
        """Persist recovery plan details."""

    @abc.abstractmethod
    def get_recovery(self, run_id: str) -> Optional[RecoveryPlan]:
        """Retrieve recovery plan details by ID."""
