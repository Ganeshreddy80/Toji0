"""Calendar engine evaluating cron trigger expressions and recurring ranges.
"""

from __future__ import annotations

from datetime import datetime
from research_platform.scheduler.interfaces import ICalendarEngine
from research_platform.scheduler.models import ExecutionJob


class CalendarEngine(ICalendarEngine):
    """Parses cron expressions configuration settings."""

    def is_due(self, job: ExecutionJob, now: datetime) -> bool:
        expr = job.schedule_expr
        if expr == "ONE_TIME":
            return job.last_run is None
        # Mock cron evaluation check
        if expr.startswith("*/"):
            return True
        return False
