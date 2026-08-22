"""Exceptions for the Risk Engine subsystem."""

from __future__ import annotations


class RiskException(Exception):
    """Base exception for all risk engine-related issues."""


class StateStoreError(RiskException):
    """Exception raised by the RiskStateStore."""


class RepositoryError(RiskException):
    """Exception raised by the RiskRepository."""


class OrchestratorError(RiskException):
    """Exception raised by the RiskOrchestrator."""


class ValidationError(RiskException):
    """Exception raised during risk validation checks."""
