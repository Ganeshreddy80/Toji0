"""Scheduler engine validating job details and queuing executions.
"""

from __future__ import annotations

from research_platform.scheduler.models import ExecutionJob


class SchedulerEngine:
    """Enqueues task records verifying correct parameter bounds."""

    def initiate_job(
        self,
        job_id: str,
        name: str,
        task_type: str,
        schedule_expr: str,
        priority: int
    ) -> ExecutionJob:
        if not job_id or not name:
            raise ValueError("Job ID and Name must not be blank.")
        if task_type not in ["BACKTEST", "PAPER_TRADING", "WALK_FORWARD", "OPTIMIZATION", "RESEARCH", "MAINTENANCE"]:
            raise ValueError("Invalid Task Type: Type must be BACKTEST, PAPER_TRADING, WALK_FORWARD, OPTIMIZATION, RESEARCH, or MAINTENANCE.")
        if priority < 0:
            raise ValueError("Invalid Priority: Weight must be positive.")

        return ExecutionJob(
            job_id=job_id,
            name=name,
            task_type=task_type,
            schedule_expr=schedule_expr,
            priority=priority
        )
