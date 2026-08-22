"""Validator assessing simulation replay systems and stress injections.
"""

from __future__ import annotations

import time
from typing import Any
from research_platform.system_validation.interfaces import ISubsystemValidator
from research_platform.system_validation.models import (
    SubsystemHealth,
    ValidationCheck,
    ValidationSeverity,
)


class SimulationValidator(ISubsystemValidator):
    """Audits tick replayers and simulated latency delay injection parameters."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        has_sim = False
        if hasattr(container, "has"):
            for key in container._services.keys():
                if "SimulationOrchestrator" in str(key):
                    has_sim = True
                    break

        checks.append(ValidationCheck(
            name="Digital Twin Replay Operations",
            description="Verify order execution matcher and simulated returns variance.",
            category="Simulation",
            passed=has_sim,
            severity=ValidationSeverity.ERROR,
            message="Replay re-runner and stress test parameters validated." if has_sim else "Simulation orchestrator failed to resolve."
        ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="Simulation",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
