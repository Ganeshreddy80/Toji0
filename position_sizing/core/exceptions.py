"""Exceptions for the Position Sizing Engine subsystem."""

from __future__ import annotations


class PositionSizingError(Exception):
    """Base exception for all position sizing-related issues."""


class StateStoreError(PositionSizingError):
    """Exception raised by the PositionSizingStateStore."""


class RepositoryError(PositionSizingError):
    """Exception raised by the PositionSizingRepository."""


class OrchestratorError(PositionSizingError):
    """Exception raised by the PositionSizingOrchestrator."""


class ValidationError(PositionSizingError):
    """Exception raised during exposure, leverage, or margin validation checks."""
