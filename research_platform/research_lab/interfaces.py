"""Abstract contracts for the Research Lab.
"""

from __future__ import annotations

import abc
from typing import List, Optional
from research_platform.research_lab.models import (
    FeatureData,
    AlphaFactor,
    Hypothesis,
    ResearchSession,
)


class IResearchLabRepository(abc.ABC):
    """Abstract contract for persisting research lab states."""

    @abc.abstractmethod
    def save_feature(self, feature: FeatureData) -> None:
        """Persist feature data."""

    @abc.abstractmethod
    def get_feature(self, feature_id: str) -> Optional[FeatureData]:
        """Retrieve feature details by ID."""

    @abc.abstractmethod
    def save_factor(self, factor: AlphaFactor) -> None:
        """Persist calculated alpha factor details."""

    @abc.abstractmethod
    def get_factor(self, factor_id: str) -> Optional[AlphaFactor]:
        """Retrieve alpha factor details by ID."""

    @abc.abstractmethod
    def save_hypothesis(self, hypo: Hypothesis) -> None:
        """Persist hypothesis test logs."""

    @abc.abstractmethod
    def get_hypothesis(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Retrieve hypothesis details by ID."""


class IFeatureStore(abc.ABC):
    """Abstract contract for extracting features."""

    @abc.abstractmethod
    def extract_features(self, name: str, data: List[float]) -> FeatureData:
        """Runs feature engineering logic."""


class IFactorEngine(abc.ABC):
    """Abstract contract for generating alpha factors."""

    @abc.abstractmethod
    def calculate_factor(self, factor_id: str, formula: str, inputs: List[float]) -> AlphaFactor:
        """Calculate factor values from mathematical inputs."""


class IHypothesisEngine(abc.ABC):
    """Abstract contract for verifying hypothesis tests."""

    @abc.abstractmethod
    def verify_hypothesis(self, hypothesis_id: str, description: str, p_value: float) -> Hypothesis:
        """Check p-values to verify hypothesis tests."""
