"""Abstract contracts for the Alpha Factory.
"""

from __future__ import annotations

import abc
from typing import List, Optional
from research_platform.alpha_factory.models import (
    AlphaSignal,
    AlphaCombo,
    EnsembleModel,
)


class IAlphaFactoryRepository(abc.ABC):
    """Abstract contract for persisting alpha signals and ensembles."""

    @abc.abstractmethod
    def save_signal(self, signal: AlphaSignal) -> None:
        """Persist alpha signal details."""

    @abc.abstractmethod
    def get_signal(self, signal_id: str) -> Optional[AlphaSignal]:
        """Retrieve alpha signal details by ID."""

    @abc.abstractmethod
    def save_combo(self, combo: AlphaCombo) -> None:
        """Persist signals combination details."""

    @abc.abstractmethod
    def get_combo(self, combo_id: str) -> Optional[AlphaCombo]:
        """Retrieve signals combination details by ID."""

    @abc.abstractmethod
    def save_ensemble(self, model: EnsembleModel) -> None:
        """Persist ensemble model details."""

    @abc.abstractmethod
    def get_ensemble(self, ensemble_id: str) -> Optional[EnsembleModel]:
        """Retrieve ensemble details by ID."""


class ISignalEngine(abc.ABC):
    """Abstract contract for generating signals."""

    @abc.abstractmethod
    def generate_signal(self, signal_id: str, factor_id: str, values: List[float]) -> AlphaSignal:
        """Translate raw factors into buy/sell signals."""


class IAlphaEngine(abc.ABC):
    """Abstract contract for combining signals into combinations."""

    @abc.abstractmethod
    def combine_signals(self, combo_id: str, signals: List[AlphaSignal], weights: List[float]) -> AlphaCombo:
        """Combine buy/sell signals based on custom weights."""


class IEnsembleEngine(abc.ABC):
    """Abstract contract for ensembling combinations."""

    @abc.abstractmethod
    def create_ensemble(self, ensemble_id: str, combos: List[AlphaCombo]) -> EnsembleModel:
        """Assemble combinations into unified ensemble models."""
