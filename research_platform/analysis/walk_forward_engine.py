"""Walk-forward evaluation framework for the Research Platform (Sprint 6)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Callable, Dict, List

from research_platform.core.enums import WalkForwardType
from research_platform.core.exceptions import WalkForwardError
from research_platform.core.interfaces import IWalkForwardFramework
from research_platform.core.models import (
    DatasetVersion,
    PerformanceMetrics,
    WalkForwardResult,
    WalkForwardWindow,
)

logger = logging.getLogger(__name__)


class WalkForwardFramework(IWalkForwardFramework):
    """Evaluates strategy stability across rolling or expanding out-of-sample windows."""

    def evaluate(
        self,
        eval_fn: Callable[[DatasetVersion, Dict[str, Any]], PerformanceMetrics],
        dataset: DatasetVersion,
        parameters: Dict[str, Any],
        train_window_ratio: float = 0.7,
        num_windows: int = 5,
    ) -> WalkForwardResult:
        """Run walk-forward window partitioning and out-of-sample metrics evaluation."""
        if not dataset or not dataset.dataset_id:
            raise WalkForwardError("Invalid dataset provided for walk-forward evaluation.")

        if num_windows < 1:
            raise WalkForwardError("num_windows must be at least 1.")

        total_duration = dataset.end_time - dataset.start_time
        if total_duration.total_seconds() <= 0:
            # Fallback for synthetic/zero duration datasets
            total_duration = timedelta(days=365)

        window_duration = total_duration / (num_windows + 1)
        windows: List[WalkForwardWindow] = []
        eff_ratios: List[float] = []

        curr_start = dataset.start_time
        for i in range(num_windows):
            is_start = curr_start
            is_end = is_start + (window_duration * train_window_ratio)
            oos_start = is_end
            oos_end = oos_start + (window_duration * (1.0 - train_window_ratio))

            # Sliced dataset representations
            is_dataset = dataset.model_copy(update={"start_time": is_start, "end_time": is_end})
            oos_dataset = dataset.model_copy(update={"start_time": oos_start, "end_time": oos_end})

            try:
                is_metrics = eval_fn(is_dataset, parameters)
                oos_metrics = eval_fn(oos_dataset, parameters)
            except Exception as e:
                logger.error("WalkForwardFramework: Window %d evaluation failed: %s", i, e)
                is_metrics = PerformanceMetrics()
                oos_metrics = PerformanceMetrics()

            eff = (oos_metrics.sharpe_ratio / is_metrics.sharpe_ratio) if is_metrics.sharpe_ratio > 0.0 else 1.0
            eff = max(0.0, min(2.0, eff))
            eff_ratios.append(eff)

            window = WalkForwardWindow(
                window_index=i,
                in_sample_start=is_start,
                in_sample_end=is_end,
                out_of_sample_start=oos_start,
                out_of_sample_end=oos_end,
                in_sample_metrics=is_metrics,
                out_of_sample_metrics=oos_metrics,
                efficiency_ratio=round(eff, 4),
            )
            windows.append(window)
            curr_start = oos_start

        avg_eff = (sum(eff_ratios) / len(eff_ratios)) if eff_ratios else 1.0
        stability_score = max(0.0, min(1.0, 1.0 - (sum(abs(e - 1.0) for e in eff_ratios) / len(eff_ratios)))) if eff_ratios else 1.0

        # Combine overall out-of-sample metrics
        overall_oos = eval_fn(dataset, parameters)

        return WalkForwardResult(
            framework_type=WalkForwardType.ROLLING,
            windows=windows,
            average_efficiency=round(avg_eff, 4),
            overall_out_of_sample_metrics=overall_oos,
            stability_score=round(stability_score, 4),
        )
