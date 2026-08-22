"""R53 Health checker — aggregates service registry presence checks."""

from __future__ import annotations

import time
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

REQUIRED_SERVICES = [
    "EventBus",
    "Database",
    "RuntimeEngine",
]

OPTIONAL_SERVICES = [
    "RecoveryOrchestrator",
    "ConfigManager",
    "AuditLogger",
    "StrategySchedulerOrchestrator",
]


class HealthChecker(IChecker):
    @property
    def name(self) -> str:
        return "PlatformHealthChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()

            missing_required = [s for s in REQUIRED_SERVICES if registry.get_service(s) is None]
            missing_optional = [s for s in OPTIONAL_SERVICES if registry.get_service(s) is None]
            duration_ms = (time.perf_counter() - start) * 1000

            if missing_required:
                return CheckResult(
                    check_name=self.name, status=CheckStatus.FAIL,
                    duration_ms=duration_ms,
                    message=f"Required services missing: {missing_required}",
                    details={"missing_required": missing_required, "missing_optional": missing_optional}
                )
            if missing_optional:
                return CheckResult(
                    check_name=self.name, status=CheckStatus.WARN,
                    duration_ms=duration_ms,
                    message=f"Optional services missing: {missing_optional}",
                    details={"missing_required": [], "missing_optional": missing_optional}
                )
            return CheckResult(
                check_name=self.name, status=CheckStatus.PASS,
                duration_ms=duration_ms,
                message="All platform services healthy",
                details={"required": REQUIRED_SERVICES, "optional": OPTIONAL_SERVICES}
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
