"""Rolling engine generating rolling optimization windows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List
from research_platform.walk_forward.interfaces import IRollingEngine
from research_platform.walk_forward.models import ValidationWindow


class RollingEngine(IRollingEngine):
    """Enforces rolling train and test range calculations."""

    def generate_rolling_windows(
        self,
        start: datetime,
        end: datetime,
        train_len_days: float,
        test_len_days: float
    ) -> List[ValidationWindow]:
        windows = []
        curr = start
        while curr + timedelta(days=train_len_days + test_len_days) <= end:
            t_start = curr
            t_end = curr + timedelta(days=train_len_days)
            te_start = t_end
            te_end = te_start + timedelta(days=test_len_days)
            
            windows.append(ValidationWindow(
                window_id=f"win-roll-{uuid.uuid4().hex[:8]}",
                train_start=t_start,
                train_end=t_end,
                test_start=te_start,
                test_end=te_end,
                in_sample_sharpe=0.0,
                out_of_sample_sharpe=0.0
            ))
            # Shift by test window length
            curr += timedelta(days=test_len_days)

        return windows
