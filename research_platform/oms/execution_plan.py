"""Execution Planner generating schedules for child orders dispatch.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from research_platform.oms.interfaces import IExecutionPlanner
from research_platform.oms.models import OrderExecutionPlan


class ExecutionPlanner(IExecutionPlanner):
    """Generates scheduled execution plans for parent algorithmic orders."""

    def __init__(self, default_interval_seconds: int = 300) -> None:
        self.default_interval_seconds = default_interval_seconds

    def generate_plan(self, parent_id: str, quantity: float, intervals: int) -> OrderExecutionPlan:
        """Generate timing schedules for parent algorithmic slicing."""
        start_time = datetime.now(timezone.utc)
        scheduled_times = []
        
        for i in range(intervals):
            scheduled_times.append(start_time + timedelta(seconds=i * self.default_interval_seconds))

        return OrderExecutionPlan(
            plan_id=str(uuid.uuid4()),
            parent_id=parent_id,
            total_quantity=quantity,
            slices_count=intervals,
            interval_seconds=self.default_interval_seconds,
            scheduled_times=scheduled_times
        )
