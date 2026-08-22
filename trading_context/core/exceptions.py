"""Exceptions for the Trading Context subsystem."""

from __future__ import annotations


class TradingContextException(Exception):
    """Base exception for all trading context-related issues."""


class StateStoreError(TradingContextException):
    """Exception raised by the TradingContextStateStore."""


class RepositoryError(TradingContextException):
    """Exception raised by the TradingContextRepository."""


class OrchestratorError(TradingContextException):
    """Exception raised by the TradingContextOrchestrator."""


class ValidationError(TradingContextException):
    """Exception raised during context validation checks."""
