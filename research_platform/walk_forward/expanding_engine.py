"""Expanding engine generating expanding optimization windows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List
from research_platform.walk_forward.interfaces import IExpandingEngine
from research_platform.walk_forward.models import ValidationWindow


class ExpandingEngine(IExpandingEngine):
    """Enforces expanding train ranges and shifting test ranges calculations."""

    def generate_expanding_windows(
        self,
        start: datetime,
        end: datetime,
        initial_train_days: float,
        test_len_days: float
    ) -> List[ValidationWindow]:
        windows = []
        curr_train_end = start + timedelta(days=initial_train_days)
        while curr_train_end + timedelta(days=test_len_days) <= end:
            t_start = start
            t_end = curr_train_end
            te_start = t_end
            te_end = te_start + timedelta(days=test_len_days)
            
            windows.append(ValidationWindow(
                window_id=f"win-exp-{uuid.uuid4().hex[:8]}",
                train_start=t_start,
                train_end=t_end,
                test_start=te_start,
                test_end=te_end,
                in_sample_sharpe=0.0,
                out_of_sample_sharpe=0.0
            ))
            # Expand train window end by test window length
            curr_train_end += timedelta(days=test_len_days)

        return windows
