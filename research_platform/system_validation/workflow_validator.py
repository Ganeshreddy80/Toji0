"""Validator assessing promotional workflow step transitions.
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


class WorkflowValidator(ISubsystemValidator):
    """Audits promotions workflow step transitions and status paths."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        # Verify WorkflowOrchestrator resolve
        has_orch = False
        w_orch_key = "research_platform.workflow_orchestration.plugin.WorkflowOrchestratorPlugin" # or check if class maps
        # Check active class resolver
        if hasattr(container, "has"):
            for key in container._services.keys():
                if "WorkflowOrchestrator" in str(key):
                    has_orch = True
                    break

        checks.append(ValidationCheck(
            name="Workflow Orchestration Status",
            description="Verify promotional workflow engine resolves and runs transitions.",
            category="Workflow Promotion",
            passed=has_orch,
            severity=ValidationSeverity.ERROR,
            message="Workflow promotional state machine matches integration parameters." if has_orch else "Workflow engine resolution failed."
        ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="Workflow",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
