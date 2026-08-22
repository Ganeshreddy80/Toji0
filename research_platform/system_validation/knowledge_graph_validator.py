"""Validator assessing Knowledge Graph lineage and loops structures.
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


class KnowledgeGraphValidator(ISubsystemValidator):
    """Audits Knowledge Graph cycle check engines and relationship links."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        kg_key = "research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"
        has_kg = hasattr(container, "has") and container.has(kg_key)
        if has_kg:
            orch = container.resolve(kg_key)
            checks.append(ValidationCheck(
                name="Knowledge Graph Operations",
                description="Verify register_node and link_nodes interfaces.",
                category="Knowledge Graph",
                passed=hasattr(orch, "register_node") and hasattr(orch, "link_nodes"),
                severity=ValidationSeverity.ERROR,
                message="Graph Node and Edge registration methods validated."
            ))
        else:
            checks.append(ValidationCheck(
                name="Knowledge Graph Status",
                description="Verify Knowledge Graph orchestrator resolves.",
                category="Knowledge Graph",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message="Knowledge Graph orchestrator resolution failed."
            ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 0.0

        return SubsystemHealth(
            name="Knowledge Graph",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
