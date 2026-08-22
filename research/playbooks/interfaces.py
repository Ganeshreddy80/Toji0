"""Abstract interfaces for reusable quantitative research workflows (playbooks)."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from research.experiments.manager import ExperimentManager
    from research.experiments.models import ResearchExperiment


class IPlaybook(abc.ABC):
    """Core contract for defining a standardized research playbook workflow."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the research playbook (e.g. 'Momentum Research')."""

    @property
    @abc.abstractmethod
    def description(self) -> str:
        """Detailed description of what kind of research is conducted."""

    @property
    @abc.abstractmethod
    def required_datasets(self) -> list[str]:
        """Expected datasets identifiers."""

    @property
    @abc.abstractmethod
    def required_features(self) -> list[str]:
        """Expected features names required from feature store."""

    @property
    @abc.abstractmethod
    def steps(self) -> list[str]:
        """Human-readable sequential execution steps."""

    @property
    @abc.abstractmethod
    def validation_criteria(self) -> dict[str, Any]:
        """Criteria thresholds (e.g. {'min_sharpe': 1.5, 'max_drawdown': 0.2})."""

    @abc.abstractmethod
    def execute(
        self,
        manager: ExperimentManager,
        dataset_ref: str,
        asset_universe: list[str],
        custom_inputs: dict[str, Any] | None = None,
    ) -> ResearchExperiment:
        """Create and register the ResearchExperiment matching this playbook."""
