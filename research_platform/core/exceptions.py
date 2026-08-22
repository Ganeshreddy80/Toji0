"""Exceptions for the Research Platform (Sprint 6)."""

from __future__ import annotations


class ResearchPlatformException(Exception):
    """Base exception for all Research Platform errors."""


class ExperimentError(ResearchPlatformException):
    """Raised when experiment configuration or execution fails validation."""


class DatasetError(ResearchPlatformException):
    """Raised when dataset loading, integrity, or versioning fails."""


class StrategyRegistryError(ResearchPlatformException):
    """Raised when strategy registration or version lookup fails."""


class MetricsCalculationError(ResearchPlatformException):
    """Raised when quantitative metrics calculation encounters invalid inputs."""


class WalkForwardError(ResearchPlatformException):
    """Raised when walk-forward window partitioning or evaluation fails."""


class ParameterSweepError(ResearchPlatformException):
    """Raised when parameter sweep config or trial execution fails."""


class ReportGenerationError(ResearchPlatformException):
    """Raised when research report generation or formatting fails."""


class RepositoryError(ResearchPlatformException):
    """Raised when experiment persistence or retrieval fails."""


class OrchestratorError(ResearchPlatformException):
    """Raised when the research orchestrator encounters a pipeline error."""
