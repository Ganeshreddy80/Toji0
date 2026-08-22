"""Ensemble engine compiling multiple combinations.
"""

from __future__ import annotations

from typing import List
from research_platform.alpha_factory.interfaces import IEnsembleEngine
from research_platform.alpha_factory.models import EnsembleModel, AlphaCombo


class EnsembleEngine(IEnsembleEngine):
    """Ensembles combinations portfolios."""

    def create_ensemble(self, ensemble_id: str, combos: List[AlphaCombo]) -> EnsembleModel:
        return EnsembleModel(
            ensemble_id=ensemble_id,
            combos=combos
        )
