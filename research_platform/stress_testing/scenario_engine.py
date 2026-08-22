"""Scenario engine defining stress scenarios parameters.
"""

from __future__ import annotations

from research_platform.stress_testing.models import StressScenario


class ScenarioEngine:
    """Builds historical and synthetic stress scenarios."""

    def create_scenario(
        self,
        scenario_id: str,
        name: str,
        shock_type: str,
        magnitude: float
    ) -> StressScenario:
        return StressScenario(
            scenario_id=scenario_id,
            name=name,
            shock_type=shock_type,
            magnitude=magnitude
        )
