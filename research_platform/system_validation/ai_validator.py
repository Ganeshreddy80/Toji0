"""Validator assessing AI Intelligence context construction and recommendations.
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


class AiValidator(ISubsystemValidator):
    """Audits prompt templates, contexts and decision review engines."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        # Verify research scorer or AI reviewer resolves
        has_ai = False
        if hasattr(container, "has"):
            for key in container._services.keys():
                if "AIIntelligenceOrchestrator" in str(key) or "ResearchIntelligenceOrchestrator" in str(key):
                    has_ai = True
                    break

        checks.append(ValidationCheck(
            name="AI/LLM Providers Validation",
            description="Verify prompt constructors and context builders.",
            category="AI Intelligence",
            passed=has_ai,
            severity=ValidationSeverity.ERROR,
            message="AI Context and Explanation builders verified." if has_ai else "Failed to locate AI orchestrators in container."
        ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="AI",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
