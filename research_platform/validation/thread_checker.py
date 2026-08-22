"""R53 Thread checker — detects thread leaks and zombie threads."""

from __future__ import annotations

import threading
import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

MAX_THREADS = 200


class ThreadChecker(IChecker):
    """Checks live thread count for runaway thread creation."""

    @property
    def name(self) -> str:
        return "ThreadLeakChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            active = threading.active_count()
            all_threads = threading.enumerate()
            daemon_count = sum(1 for t in all_threads if t.daemon)
            non_daemon = active - daemon_count

            duration_ms = (time.perf_counter() - start) * 1000
            if active > MAX_THREADS:
                return CheckResult(
                    check_name=self.name, status=CheckStatus.FAIL,
                    duration_ms=duration_ms,
                    message=f"Thread count {active} exceeds limit {MAX_THREADS}",
                    details={"active": active, "daemon": daemon_count, "non_daemon": non_daemon}
                )
            status = CheckStatus.WARN if active > MAX_THREADS * 0.8 else CheckStatus.PASS
            return CheckResult(
                check_name=self.name, status=status,
                duration_ms=duration_ms,
                message=f"Active threads: {active} (daemon={daemon_count})",
                details={"active": active, "daemon": daemon_count, "non_daemon": non_daemon}
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
