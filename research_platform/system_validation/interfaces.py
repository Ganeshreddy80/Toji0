"""Abstract contracts for the System Validation Framework.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.system_validation.models import (
    SubsystemHealth,
    SystemCertificationCard,
    ValidationCheck,
)


class ISubsystemValidator(abc.ABC):
    """Abstract contract for validating a specific category or component."""

    @abc.abstractmethod
    def validate(self, container: Any) -> SubsystemHealth:
        """Execute validation checks against container components."""


class IValidationRepository(abc.ABC):
    """Abstract contract for persisting validation and health cards."""

    @abc.abstractmethod
    def save_health(self, health: SubsystemHealth) -> None:
        """Persist a subsystem's health card."""

    @abc.abstractmethod
    def list_health_cards(self) -> List[SubsystemHealth]:
        """List all registered health cards."""

    @abc.abstractmethod
    def save_certification(self, cert: SystemCertificationCard) -> None:
        """Persist final system certification card."""

    @abc.abstractmethod
    def get_latest_certification(self) -> Optional[SystemCertificationCard]:
        """Retrieve latest certification log."""


class IValidationOrchestrator(abc.ABC):
    """Abstract contract for validation orchestrators."""
    pass
