"""Retry engine evaluating backoffs and decrements for execution retries.
"""

from __future__ import annotations

from research_platform.scheduler.interfaces import IRetryEngine
from research_platform.scheduler.models import ExecutionJob


class RetryEngine(IRetryEngine):
    """Triggers task repeats on callback failures."""

    def evaluate_retry(self, job: ExecutionJob) -> bool:
        return job.retries_left > 0
