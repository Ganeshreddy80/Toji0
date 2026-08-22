"""Reproducibility engine verifying parameter match hashes across runs.
"""

from __future__ import annotations

from research_platform.experiment_manager.interfaces import IReproducibilityEngine
from research_platform.experiment_manager.models import ReproducibilitySnapshot


class ReproducibilityEngine(IReproducibilityEngine):
    """Checks seed snapshots matching parameters format."""

    def verify_reproducibility(self, first: ReproducibilitySnapshot, second: ReproducibilitySnapshot) -> bool:
        return (
            first.random_seed == second.random_seed and
            first.dataset_hash == second.dataset_hash and
            first.git_hash == second.git_hash and
            first.config_id == second.config_id
        )
