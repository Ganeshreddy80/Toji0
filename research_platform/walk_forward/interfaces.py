"""Abstract contracts for Walk Forward Validation.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import List, Optional
from research_platform.walk_forward.models import (
    ValidationWindow,
    SensitivityScore,
    OverfittingCard,
)


class IWalkForwardRepository(abc.ABC):
    """Abstract contract for persisting walk forward results."""

    @abc.abstractmethod
    def save_window(self, window: ValidationWindow) -> None:
        """Persist validation window details."""

    @abc.abstractmethod
    def get_window(self, window_id: str) -> Optional[ValidationWindow]:
        """Retrieve window details by ID."""

    @abc.abstractmethod
    def save_sensitivity(self, score: SensitivityScore) -> None:
        """Persist parameter sensitivity analysis log."""

    @abc.abstractmethod
    def get_sensitivity(self, parameter_name: str) -> Optional[SensitivityScore]:
        """Retrieve parameter sensitivity logs by parameter name."""

    @abc.abstractmethod
    def save_overfitting(self, card: OverfittingCard) -> None:
        """Persist overfitting diagnostics details."""

    @abc.abstractmethod
    def get_overfitting(self, strategy_id: str) -> Optional[OverfittingCard]:
        """Retrieve overfitting card details by strategy ID."""


class IRollingEngine(abc.ABC):
    """Abstract contract for rolling validation ranges."""

    @abc.abstractmethod
    def generate_rolling_windows(
        self,
        start: datetime,
        end: datetime,
        train_len_days: float,
        test_len_days: float
    ) -> List[ValidationWindow]:
        """Generate rolling optimization windows."""


class IExpandingEngine(abc.ABC):
    """Abstract contract for expanding validation ranges."""

    @abc.abstractmethod
    def generate_expanding_windows(
        self,
        start: datetime,
        end: datetime,
        initial_train_days: float,
        test_len_days: float
    ) -> List[ValidationWindow]:
        """Generate expanding optimization windows."""


class IValidationEngine(abc.ABC):
    """Abstract contract for evaluating walk forward returns."""

    @abc.abstractmethod
    def validate_window(self, window: ValidationWindow, in_sample_sharpe: float, out_of_sample_sharpe: float) -> ValidationWindow:
        """Score window in sample and out of sample statistics."""


class IRobustnessEngine(abc.ABC):
    """Abstract contract for parameter sensitivities analysis."""

    @abc.abstractmethod
    def analyze_sensitivity(self, parameter_name: str, values: List[float], outcomes: List[float]) -> SensitivityScore:
        """Score parameters sensitivity index variations."""


class IStabilityEngine(abc.ABC):
    """Abstract contract for overfitting check calculations."""

    @abc.abstractmethod
    def detect_overfitting(self, strategy_id: str, is_overfitted: bool, stability_score: float) -> OverfittingCard:
        """Compile overfitting probabilities diagnostics summary."""
