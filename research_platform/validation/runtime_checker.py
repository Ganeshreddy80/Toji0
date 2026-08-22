"""R53 Runtime checker — verifies runtime engine loop status via service registry."""

from __future__ import annotations

import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class RuntimeChecker(IChecker):
    @property
    def name(self) -> str:
        return "RuntimeEngineChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            engine = registry.get_service("RuntimeEngine")
            duration_ms = (time.perf_counter() - start) * 1000
            if engine is None:
                return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                                   duration_ms=duration_ms,
                                   message="RuntimeEngine not registered in service registry")
            status_attr = getattr(engine, "status", None) or getattr(engine, "_status", None)
            return CheckResult(
                check_name=self.name, status=CheckStatus.PASS,
                duration_ms=duration_ms,
                message=f"RuntimeEngine present, status={status_attr}",
                details={"status": str(status_attr)}
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
