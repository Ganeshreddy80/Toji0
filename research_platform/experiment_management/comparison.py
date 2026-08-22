"""Experiment comparison diff compiler.
"""

from __future__ import annotations

import logging
import uuid
from typing import List
from research_platform.experiment_management.interfaces import IExperimentComparer
from research_platform.experiment_management.models import ExperimentComparison, ExperimentRecord

logger = logging.getLogger(__name__)


class ExperimentComparer(IExperimentComparer):
    """Compares parameters and metrics across multiple quantitative experiments side-by-side."""

    def compare_experiments(self, records: List[ExperimentRecord]) -> ExperimentComparison:
        """Compile parameters diff and output comparative matrices."""
        compared_ids = [r.experiment_id for r in records]

        parameter_diffs = {}
        metrics_comparison = {}

        # 1. Collect all parameter keys
        all_keys = set()
        for r in records:
            all_keys.update(r.parameters.keys())
            metrics_comparison[r.experiment_id] = r.metrics

        # 2. Find keys where values differ across records
        for key in all_keys:
            vals = []
            for r in records:
                vals.append(r.parameters.get(key))

            # If values differ (or not present in all), record diff
            if len(set(str(v) for v in vals)) > 1:
                parameter_diffs[key] = {r.experiment_id: r.parameters.get(key) for r in records}

        comp = ExperimentComparison(
            comparison_id=f"comp-{uuid.uuid4().hex[:8]}",
            compared_ids=compared_ids,
            parameter_diffs=parameter_diffs,
            metrics_comparison=metrics_comparison
        )
        logger.info("Compiled experiment comparison report '%s' for %d records.",
                    comp.comparison_id, len(records))
        return comp
