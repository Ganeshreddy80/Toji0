"""R53 Recovery checker — verifies the recovery orchestrator is active."""

from __future__ import annotations

import time
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus


class RecoveryChecker(IChecker):
    @property
    def name(self) -> str:
        return "RecoveryChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            recovery = ServiceRegistry().get_service("RecoveryOrchestrator") \
                or ServiceRegistry().get_service("RecoveryEngine")
            duration_ms = (time.perf_counter() - start) * 1000
            if recovery is None:
                return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                                   duration_ms=duration_ms, message="RecoveryOrchestrator not found in DI")
            return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                               duration_ms=duration_ms, message="Recovery system registered and available")
        except Exception as e:
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=(time.perf_counter() - start) * 1000, message=str(e))
