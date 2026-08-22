"""R53 Burn-in test — intensive resource saturation test to surface stability failures.

Runs all checkers in rapid succession repeatedly for the configured duration.
"""

from __future__ import annotations

import time
import logging
from typing import List
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class BurnInTest(IChecker):
    """Exhaustively cycles all provided checkers for a set duration to surface failures."""

    def __init__(self, checkers: List[IChecker], duration_sec: float = 5.0) -> None:
        self.checkers = checkers
        self.duration_sec = duration_sec

    @property
    def name(self) -> str:
        return "BurnInTest"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        deadline = start + self.duration_sec
        total_runs = 0
        failures: List[str] = []

        while time.perf_counter() < deadline:
            for checker in self.checkers:
                try:
                    result = checker.run()
                    total_runs += 1
                    if result.status == CheckStatus.FAIL:
                        failures.append(f"{checker.name}: {result.message}")
                except Exception as e:
                    failures.append(f"{checker.name}: EXCEPTION {e}")
                    total_runs += 1

        duration_ms = (time.perf_counter() - start) * 1000
        if failures:
            return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                               duration_ms=duration_ms,
                               message=f"Burn-in failed: {len(failures)} failures in {total_runs} runs",
                               details={"failures": failures[:20], "total_runs": total_runs})
        return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                           duration_ms=duration_ms,
                           message=f"Burn-in PASS: {total_runs} checker runs, 0 failures",
                           details={"total_runs": total_runs, "duration_sec": self.duration_sec})
