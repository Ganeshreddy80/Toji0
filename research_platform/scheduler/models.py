"""Immutable Pydantic models for the Strategy Scheduler.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExecutionJob(BaseModel):
    """An execution task managed by the scheduler."""

    job_id: str
    name: str
    task_type: str  # BACKTEST, PAPER_TRADING, WALK_FORWARD, OPTIMIZATION, RESEARCH
    schedule_expr: str  # Cron expression or ONE_TIME
    priority: int  # Priority weight
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, CANCELED
    retries_left: int = 3
    last_run: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class ExecutionHistoryCard(BaseModel):
    """Execution status report details."""

    job_id: str
    status: str
    error_message: Optional[str] = None
    duration_sec: float
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class PriorityQueueCard(BaseModel):
    """Statistics card detailing active queued jobs count."""

    queue_name: str
    jobs_count: int

    model_config = ConfigDict(frozen=True)
