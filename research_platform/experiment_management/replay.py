"""Experiment replayer verifying reproducibility tolerances.
"""

from __future__ import annotations

import logging
import uuid
from typing import Dict
from research_platform.experiment_management.interfaces import IExperimentReplayer
from research_platform.experiment_management.models import ExperimentRecord, ReproducibilityCheck

logger = logging.getLogger(__name__)


class ExperimentReplayer(IExperimentReplayer):
    """Replays run results and compares metric differences to check reproducibility."""

    def replay_experiment(
        self,
        original: ExperimentRecord,
        replayed_metrics: Dict[str, float],
        replayed_code_hash: str
    ) -> ReproducibilityCheck:
        """Verify metrics variance and code hash matches between logs."""
        hash_matched = original.code_hash == replayed_code_hash

        metrics_matched = True
        # Verify deviations on each metric (tolerance of 1e-5)
        for key, original_val in original.metrics.items():
            replayed_val = replayed_metrics.get(key)
            if replayed_val is None:
                metrics_matched = False
                break
            
            if abs(original_val - replayed_val) > 0.00001:
                metrics_matched = False
                logger.warning("Reproducibility deviation on metric '%s': Original=%.4f, Replayed=%.4f",
                               key, original_val, replayed_val)

        matched = hash_matched and metrics_matched

        check = ReproducibilityCheck(
            check_id=f"rep-{uuid.uuid4().hex[:8]}",
            experiment_id=original.experiment_id,
            original_metrics=original.metrics,
            replayed_metrics=replayed_metrics,
            original_hash=original.code_hash,
            replayed_hash=replayed_code_hash,
            matched=matched
        )
        logger.info("Reproducibility check completed for experiment '%s'. Matched: %s",
                    original.experiment_id, matched)
        return check
