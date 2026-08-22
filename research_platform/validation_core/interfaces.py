"""Abstract contracts for the Validation Core.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.validation_core.models import (
    ValidationConfiguration,
    ValidationReport,
    ValidationRun
)


class IValidationRepository(abc.ABC):
    """Abstract database repository contract for validation persistence."""

    @abc.abstractmethod
    def save_run(self, run: ValidationRun) -> None:
        """Persist validation run progress or result."""

    @abc.abstractmethod
    def get_run(self, run_id: str) -> Optional[ValidationRun]:
        """Fetch validation run by unique ID."""

    @abc.abstractmethod
    def list_runs(self) -> List[ValidationRun]:
        """Fetch all validation runs."""


class IValidationCoreOrchestrator(abc.ABC):
    """Abstract contract for the main Validation Core coordinator."""

    @abc.abstractmethod
    def validate_strategy(self, config: ValidationConfiguration, dataset_id: str) -> ValidationReport:
        """Execute cross-validation, overfitting checks, and return validation reports."""
