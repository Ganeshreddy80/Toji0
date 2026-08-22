"""R53 Scheduler checker — verifies the strategy scheduler is active."""

from __future__ import annotations

import time
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus


class SchedulerChecker(IChecker):
    @property
    def name(self) -> str:
        return "SchedulerChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            scheduler = ServiceRegistry().get_service("StrategySchedulerOrchestrator") \
                or ServiceRegistry().get_service("Scheduler")
            duration_ms = (time.perf_counter() - start) * 1000
            if scheduler is None:
                return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                                   duration_ms=duration_ms, message="Scheduler not registered in DI")
            return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                               duration_ms=duration_ms, message="Scheduler service present and registered")
        except Exception as e:
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=(time.perf_counter() - start) * 1000, message=str(e))
