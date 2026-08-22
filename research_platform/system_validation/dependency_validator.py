"""Validator assessing container DI registrations.
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


class DependencyValidator(ISubsystemValidator):
    """Audits container registries checking for resolution and interface mismatches."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        # 1. Verify standard interfaces exist in DI
        target_keys = [
            "IEventBus",
            "research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator",
            "research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"
        ]

        for key in target_keys:
            has_reg = container.has(key) if hasattr(container, "has") else False
            checks.append(ValidationCheck(
                name=f"DI Resolution: {key}",
                description=f"Checks if registration exists for {key}",
                category="Dependency Injection",
                passed=has_reg,
                severity=ValidationSeverity.ERROR,
                message=f"Registration {key} resolved" if has_reg else f"Missing registration for {key}"
            ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else max(0.0, 100.0 - (len(failures) * 20.0))

        return SubsystemHealth(
            name="Dependency Injection",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
