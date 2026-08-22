"""R53 Performance checker — measures CPU and memory usage via psutil."""

from __future__ import annotations

import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

CPU_WARN_PCT = 70.0
CPU_FAIL_PCT = 90.0
MEM_WARN_MB = 400.0
MEM_FAIL_MB = 800.0


class PerformanceChecker(IChecker):
    @property
    def name(self) -> str:
        return "PerformanceResourceChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            import psutil
            proc = psutil.Process()
            cpu_pct = proc.cpu_percent(interval=0.1)
            mem_mb = proc.memory_info().rss / (1024 * 1024)
            duration_ms = (time.perf_counter() - start) * 1000

            if cpu_pct > CPU_FAIL_PCT or mem_mb > MEM_FAIL_MB:
                return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                                   duration_ms=duration_ms,
                                   message=f"Resource critical: CPU={cpu_pct:.1f}%, MEM={mem_mb:.1f} MB",
                                   details={"cpu_pct": cpu_pct, "mem_mb": mem_mb})
            if cpu_pct > CPU_WARN_PCT or mem_mb > MEM_WARN_MB:
                return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                                   duration_ms=duration_ms,
                                   message=f"Resource elevated: CPU={cpu_pct:.1f}%, MEM={mem_mb:.1f} MB",
                                   details={"cpu_pct": cpu_pct, "mem_mb": mem_mb})
            return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                               duration_ms=duration_ms,
                               message=f"CPU={cpu_pct:.1f}%, MEM={mem_mb:.1f} MB",
                               details={"cpu_pct": cpu_pct, "mem_mb": mem_mb})
        except ImportError:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.SKIP,
                               duration_ms=duration_ms, message="psutil not installed — skipping")
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
