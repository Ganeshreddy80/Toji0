"""Abstract contracts for the Strategy Scheduler.
"""

from __future__ import annotations

import abc
from typing import List, Optional
from research_platform.scheduler.models import ExecutionJob, ExecutionHistoryCard


class IJobRepository(abc.ABC):
    """Abstract contract for persisting scheduled jobs."""

    @abc.abstractmethod
    def save_job(self, job: ExecutionJob) -> None:
        """Persist execution job status states."""

    @abc.abstractmethod
    def get_job(self, job_id: str) -> Optional[ExecutionJob]:
        """Retrieve job details by ID."""

    @abc.abstractmethod
    def list_jobs(self) -> List[ExecutionJob]:
        """List all jobs."""

    @abc.abstractmethod
    def save_history(self, card: ExecutionHistoryCard) -> None:
        """Persist job run outcomes."""

    @abc.abstractmethod
    def get_history(self, job_id: str) -> List[ExecutionHistoryCard]:
        """List run outcomes logs matching job ID."""


class ISchedulerEngine(abc.ABC):
    """Abstract contract for scheduling engines."""

    @abc.abstractmethod
    def schedule_job(
        self,
        job_id: str,
        name: str,
        task_type: str,
        schedule_expr: str,
        priority: int
    ) -> ExecutionJob:
        """Enqueue task job verifying parameters formatting."""


class IJobExecutor(abc.ABC):
    """Abstract contract for callback executions."""

    @abc.abstractmethod
    def execute_job(self, job_id: str, callback: Any) -> ExecutionHistoryCard:
        """Run task callbacks executing within configured limits."""


class ICalendarEngine(abc.ABC):
    """Abstract contract for checking calendar schedules."""

    @abc.abstractmethod
    def is_due(self, job: ExecutionJob, now: datetime) -> bool:
        """Verify cron scheduling parameters to assess trigger requirements."""


class IRetryEngine(abc.ABC):
    """Abstract contract for execution retries backoffs."""

    @abc.abstractmethod
    def evaluate_retry(self, job: ExecutionJob) -> bool:
        """Evaluate retry counts and update fail states."""
from typing import Any
from datetime import datetime
