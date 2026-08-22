"""Job executor running callbacks and catching runtime failures.
"""

from __future__ import annotations

import time
from typing import Any
from research_platform.scheduler.models import ExecutionHistoryCard


class JobExecutor:
    """Executes execution callbacks catching timeouts and system errors."""

    def execute(self, job_id: str, callback: Any) -> ExecutionHistoryCard:
        start = time.perf_counter()
        error = None
        status = "COMPLETED"

        try:
            if callback:
                callback()
        except Exception as e:
            status = "FAILED"
            error = str(e)

        elapsed = time.perf_counter() - start
        
        return ExecutionHistoryCard(
            job_id=job_id,
            status=status,
            error_message=error,
            duration_sec=elapsed
        )
