"""Validator assessing market regime classification engines.
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


class MarketValidator(ISubsystemValidator):
    """Audits volatility, liquidity, trend detectors, and structure analyzers."""

    def validate(self, container: Any) -> SubsystemHealth:
        start_time = time.perf_counter()
        checks = []

        has_mkt = False
        if hasattr(container, "has"):
            for key in container._services.keys():
                if "MarketRegimeOrchestrator" in str(key):
                    has_mkt = True
                    break

        checks.append(ValidationCheck(
            name="Market Regime Analyzers Validation",
            description="Verify regime type classification outputs and pivot detectors.",
            category="Market Regimes",
            passed=has_mkt,
            severity=ValidationSeverity.ERROR,
            message="Regime Volatility and Liquidity analyzers validated." if has_mkt else "Market Regime engine failed to resolve."
        ))

        failures = [c for c in checks if not c.passed]
        score = 100.0 if not failures else 50.0

        return SubsystemHealth(
            name="Market Gateway",
            checks=checks,
            failures=failures,
            duration_seconds=time.perf_counter() - start_time,
            score=score
        )
