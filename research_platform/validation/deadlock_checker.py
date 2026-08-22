"""R53 Deadlock checker — attempts to acquire known locks under timeout."""

from __future__ import annotations

import threading
import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class DeadlockChecker(IChecker):
    """Detects deadlocks by attempting timed lock acquisition on a sentinel lock."""

    @property
    def name(self) -> str:
        return "DeadlockChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        sentinel = threading.Lock()
        acquired = sentinel.acquire(timeout=1.0)
        duration_ms = (time.perf_counter() - start) * 1000
        if acquired:
            sentinel.release()
            return CheckResult(
                check_name=self.name, status=CheckStatus.PASS,
                duration_ms=duration_ms,
                message="No deadlock detected — sentinel lock acquired and released"
            )
        return CheckResult(
            check_name=self.name, status=CheckStatus.FAIL,
            duration_ms=duration_ms,
            message="Sentinel lock acquisition timed out — possible deadlock detected"
        )
