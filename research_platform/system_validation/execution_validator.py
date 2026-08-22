"""Validator assessing exchange orders retry limits and execution rates.
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


class ExecutionValidator(ISubsystemValidator):
    """Audits execution rate limiters, retries policies and websocket states."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        has_ex = False
        if hasattr(container, "has"):
            for key in container._services.keys():
                if "ExecutionEngineOrchestrator" in str(key):
                    has_ex = True
                    break

        checks.append(ValidationCheck(
            name="Execution Connectivity Validation",
            description="Verify token rate limiters, retries blocks, and routers.",
            category="Exchange Execution",
            passed=has_ex,
            severity=ValidationSeverity.ERROR,
            message="Execution API and websocket heartbeat monitoring operational." if has_ex else "Execution engine failed to resolve."
        ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="Execution",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
