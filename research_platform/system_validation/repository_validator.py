"""Validator assessing repository lock operations.
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


class RepositoryValidator(ISubsystemValidator):
    """Audits repositories locking patterns and thread safety."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        # Resolve target repositories and check if they have locks
        repo_names = [
            ("Institutional Memory", "research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"),
            ("Knowledge Graph", "research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        ]

        for label, rkey in repo_names:
            has_lock = False
            if hasattr(container, "has") and container.has(rkey):
                orch = container.resolve(rkey)
                if hasattr(orch, "repository") and hasattr(orch.repository, "_lock"):
                    has_lock = True

            checks.append(ValidationCheck(
                name=f"Thread Safety: {label}",
                description=f"Verify thread locking structures exist inside {label} repository.",
                category="Thread Safety",
                passed=has_lock,
                severity=ValidationSeverity.ERROR,
                message=f"{label} has safe lock primitives." if has_lock else f"{label} repository lock is missing or not resolved."
            ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="Repositories",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
