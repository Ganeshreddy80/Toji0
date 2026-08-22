"""Abstract interfaces for versioned and cached feature calculations."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


class IFeatureDefinition(abc.ABC):
    """Abstract contract for specifying a feature computation logic."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the feature (e.g. 'RSI')."""

    @property
    @abc.abstractmethod
    def version(self) -> str:
        """Semantic version of the feature calculation logic."""

    @property
    def dependencies(self) -> list[str]:
        """Feature names this feature depends on."""
        return []

    @abc.abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate the feature values using the input DataFrame.

        Returns:
            DataFrame with the calculated feature columns appended.
        """


class IFeatureStore(abc.ABC):
    """Abstract contract for reading and writing computed features."""

    @abc.abstractmethod
    def get_features(
        self,
        symbol: str,
        features: list[tuple[str, str]],  # List of (feature_name, version)
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Retrieve computed features over date range, combining them into one DataFrame."""

    @abc.abstractmethod
    def save_features(
        self,
        symbol: str,
        feature_name: str,
        version: str,
        data: pd.DataFrame,
    ) -> None:
        """Persist computed features to the caching/storage layer."""
