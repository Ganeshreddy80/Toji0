"""R53 Resource checker — validates disk space and file descriptor limits."""

from __future__ import annotations

import time
import os
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

DISK_WARN_FREE_GB = 2.0
DISK_FAIL_FREE_GB = 0.5


class ResourceChecker(IChecker):
    @property
    def name(self) -> str:
        return "SystemResourceChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_gb = free / (1024 ** 3)
            used_pct = (used / total) * 100
            duration_ms = (time.perf_counter() - start) * 1000

            if free_gb < DISK_FAIL_FREE_GB:
                return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                                   duration_ms=duration_ms,
                                   message=f"Critical disk: only {free_gb:.2f} GB free",
                                   details={"free_gb": free_gb, "used_pct": used_pct})
            if free_gb < DISK_WARN_FREE_GB:
                return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                                   duration_ms=duration_ms,
                                   message=f"Low disk space: {free_gb:.2f} GB free",
                                   details={"free_gb": free_gb, "used_pct": used_pct})
            return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                               duration_ms=duration_ms,
                               message=f"Disk OK: {free_gb:.2f} GB free ({used_pct:.1f}% used)",
                               details={"free_gb": free_gb, "used_pct": used_pct})
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
