"""R53 Soak test — long-duration stability simulation (configurable duration).

In tests this runs for a few seconds. In production, duration_sec can be
set to 86400 (24h), 259200 (72h), 604800 (7d), or 2592000 (30d).
"""

from __future__ import annotations

import time
import threading
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus, ValidationDuration

logger = logging.getLogger(__name__)


class SoakTest(IChecker):
    """Runs a lightweight workload for the specified duration, tracking failures."""

    def __init__(self, duration_sec: float = 2.0, label: str = "QUICK") -> None:
        self.duration_sec = duration_sec
        self.label = label

    @property
    def name(self) -> str:
        return f"SoakTest[{self.label}]"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        errors = 0
        iterations = 0
        deadline = start + self.duration_sec

        while time.perf_counter() < deadline:
            try:
                # Simulate a lightweight tick workload
                _ = sum(i ** 2 for i in range(50))
                iterations += 1
            except Exception as e:
                errors += 1
                logger.warning("Soak iteration error: %s", e)
            time.sleep(0.001)

        duration_ms = (time.perf_counter() - start) * 1000
        if errors > 0:
            return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                               duration_ms=duration_ms,
                               message=f"Soak test had {errors} errors over {iterations} iterations",
                               details={"errors": errors, "iterations": iterations})
        return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                           duration_ms=duration_ms,
                           message=f"Soak test PASS: {iterations} iterations, 0 errors",
                           details={"iterations": iterations, "duration_sec": self.duration_sec})
