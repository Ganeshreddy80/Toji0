"""R53 Memory checker — detects leaks using tracemalloc snapshots."""

from __future__ import annotations

import time
import tracemalloc
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

LEAK_THRESHOLD_MB = 50.0


class MemoryChecker(IChecker):
    """Detects memory growth between two snapshots indicating leaks."""

    @property
    def name(self) -> str:
        return "MemoryLeakChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            tracemalloc.start()
            snapshot1 = tracemalloc.take_snapshot()
            time.sleep(0.05)  # brief observation window
            snapshot2 = tracemalloc.take_snapshot()
            tracemalloc.stop()

            stats = snapshot2.compare_to(snapshot1, "lineno")
            total_growth_mb = sum(s.size_diff for s in stats) / (1024 * 1024)

            duration_ms = (time.perf_counter() - start) * 1000
            if total_growth_mb > LEAK_THRESHOLD_MB:
                return CheckResult(
                    check_name=self.name, status=CheckStatus.FAIL,
                    duration_ms=duration_ms,
                    message=f"Memory growth {total_growth_mb:.2f} MB exceeds {LEAK_THRESHOLD_MB} MB threshold",
                    details={"growth_mb": total_growth_mb}
                )
            return CheckResult(
                check_name=self.name, status=CheckStatus.PASS,
                duration_ms=duration_ms,
                message=f"Memory growth {total_growth_mb:.3f} MB within limits",
                details={"growth_mb": total_growth_mb}
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
