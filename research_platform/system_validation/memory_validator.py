"""Validator assessing memory reconstruction and persistence query latency.
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


class MemoryValidator(ISubsystemValidator):
    """Audits Institutional Memory database storage and query speeds."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        m_key = "research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"
        has_mem = hasattr(container, "has") and container.has(m_key)
        if has_mem:
            orch = container.resolve(m_key)
            # Perform query test
            t0 = time.perf_counter()
            orch.repository.list_memories_by_category("test_cat")
            query_time_ms = (time.perf_counter() - t0) * 1000.0

            checks.append(ValidationCheck(
                name="Memory Query Speed",
                description="Verify query read latency is under performance benchmarks.",
                category="Institutional Memory",
                passed=query_time_ms < 10.0,
                severity=ValidationSeverity.WARNING,
                message=f"Memory read execution completed in {query_time_ms:.4f} ms."
            ))
        else:
            checks.append(ValidationCheck(
                name="Memory Resolve Status",
                description="Verify Memory Orchestrator resolution.",
                category="Institutional Memory",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message="Memory Orchestrator failed to resolve."
            ))

        failures = [c for c in checks if not c.passed and c.severity == ValidationSeverity.ERROR]
        score = 100.0 if not failures else 0.0

        return SubsystemHealth(
            name="Memory",
            checks=checks,
            failures=[c for c in checks if not c.passed],
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
