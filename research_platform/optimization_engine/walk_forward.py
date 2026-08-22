"""Walk-Forward Optimization parameter windows generator.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from research_platform.optimization_engine.models import ParameterCombination, WalkForwardWindow


class WalkForwardOptimizer:
    """Generates expanding or rolling parameters verification windows."""

    @staticmethod
    def generate_windows(
        start_time: datetime,
        end_time: datetime,
        train_days: int = 90,
        test_days: int = 30,
        step_days: int = 30,
        anchored: bool = False
    ) -> List[WalkForwardWindow]:
        """Generate rolling/anchored training & forward testing datetime splits.

        Args:
            start_time: Datetime starting bound.
            end_time: Datetime ending bound.
            train_days: Number of days in the in-sample (IS) window.
            test_days: Number of days in the out-of-sample (OOS) window.
            step_days: Step shift between consecutive windows.
            anchored: If True, the start_time is fixed (expanding window).

        Returns:
            List of WalkForwardWindow definitions.
        """
        # Ensure timezone UTC compatibility
        start = start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
            
        end = end_time
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        windows = []
        curr_start = start
        
        while True:
            train_end = curr_start + timedelta(days=train_days)
            test_end = train_end + timedelta(days=test_days)
            
            if test_end > end:
                break
                
            windows.append(
                WalkForwardWindow(
                    window_id=str(uuid.uuid4()),
                    train_start=curr_start,
                    train_end=train_end,
                    test_start=train_end,
                    test_end=test_end,
                    best_parameters=ParameterCombination(),
                    in_sample_score=0.0,
                    out_of_sample_score=0.0
                )
            )
            
            # Step shift
            if anchored:
                # anchor fixed, train size expands: curr_start stays same, train_days expands implicitly by incrementing train_end
                train_days += step_days
            else:
                curr_start += timedelta(days=step_days)

        return windows
