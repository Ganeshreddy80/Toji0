"""R53 Continuous Validation Interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from research_platform.validation.models import CheckResult, ValidationRun


class IChecker(ABC):
    """Abstract contract for a single validation check unit."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique check name."""
        pass

    @abstractmethod
    def run(self) -> CheckResult:
        """Execute the check and return a structured result."""
        pass


class IValidationOrchestrator(ABC):
    """Abstract contract for orchestrating multiple checkers in a run."""

    @abstractmethod
    def run_all(self) -> ValidationRun:
        """Execute all registered checkers and aggregate results."""
        pass
