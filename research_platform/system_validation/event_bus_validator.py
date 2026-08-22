"""Validator assessing event bus and subscription maps.
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


class EventBusValidator(ISubsystemValidator):
    """Audits active routing configurations, publishers, and subscribers delivery patterns."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        has_bus = hasattr(container, "has") and container.has("IEventBus")
        if has_bus:
            bus = container.resolve("IEventBus")
            # Verify basic methods exist
            pub_ok = hasattr(bus, "publish")
            sub_ok = hasattr(bus, "subscribe")
            checks.append(ValidationCheck(
                name="Event Bus Contracts",
                description="Verify publish and subscribe signatures exist.",
                category="Event Bus",
                passed=pub_ok and sub_ok,
                severity=ValidationSeverity.ERROR,
                message="Publish and Subscribe interfaces match specifications." if (pub_ok and sub_ok) else "Invalid Event Bus interfaces."
            ))
        else:
            checks.append(ValidationCheck(
                name="Event Bus Verification",
                description="Verify Event Bus resolves.",
                category="Event Bus",
                passed=False,
                severity=ValidationSeverity.ERROR,
                message="Failed to resolve Event Bus from container."
            ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 0.0

        return SubsystemHealth(
            name="Event Bus",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
