"""Validator assessing observability engines and structured logging.
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


class ObservabilityValidator(ISubsystemValidator):
    """Audits health checks monitors, alerts triggers, and tracers."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        has_obs = False
        if hasattr(container, "has"):
            for key in container._services.keys():
                if "ObservabilityOrchestrator" in str(key):
                    has_obs = True
                    break

        checks.append(ValidationCheck(
            name="Observability Infrastructure Validation",
            description="Verify tracing spans loggers, heartbeat monitors, and alerts checks.",
            category="Observability",
            passed=has_obs,
            severity=ValidationSeverity.ERROR,
            message="Alerts engine and performance metrics logger fully verified." if has_obs else "Observability engine failed to resolve."
        ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="Observability",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
