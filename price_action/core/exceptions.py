"""Custom exceptions for the Price Action Engine."""

from __future__ import annotations


class PriceActionException(Exception):
    """Base exception class for all Price Action Engine errors."""


class StateStoreError(PriceActionException):
    """Raised when state store operations fail or validate invalid symbols."""


class RepositoryError(PriceActionException):
    """Raised when persistence, retrieval, or loading operations encounter errors."""


class OrchestratorError(PriceActionException):
    """Raised when orchestrator fails to run the execution pipeline."""


class DetectorRegistrationError(PriceActionException):
    """Raised when there is an issue registering or removing pluggable pattern detectors."""
