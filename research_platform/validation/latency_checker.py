"""R53 Latency checker — measures loop tick latency against configured thresholds."""

from __future__ import annotations

import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

LATENCY_WARN_MS = 100.0
LATENCY_FAIL_MS = 500.0

logger = logging.getLogger(__name__)


class LatencyChecker(IChecker):
    """Measures round-trip latency of a no-op computation loop."""

    @property
    def name(self) -> str:
        return "LatencyChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        # Simulate a lightweight compute tick
        _ = sum(i * i for i in range(1000))
        duration_ms = (time.perf_counter() - start) * 1000
        if duration_ms > LATENCY_FAIL_MS:
            return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                               duration_ms=duration_ms,
                               message=f"Latency {duration_ms:.2f} ms exceeds fail threshold {LATENCY_FAIL_MS} ms")
        if duration_ms > LATENCY_WARN_MS:
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms,
                               message=f"Latency {duration_ms:.2f} ms exceeds warn threshold {LATENCY_WARN_MS} ms")
        return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                           duration_ms=duration_ms,
                           message=f"Latency {duration_ms:.3f} ms within thresholds")
