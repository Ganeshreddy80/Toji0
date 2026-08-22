"""Exceptions for the Confluence Engine."""

from __future__ import annotations


class ConfluenceException(Exception):
    """Base exception for all Confluence Engine errors."""


class OrchestratorError(ConfluenceException):
    """Raised when orchestrator execution or initialization fails."""


class RepositoryError(ConfluenceException):
    """Raised when database or persistence operations fail."""


class StateStoreError(ConfluenceException):
    """Raised when in-memory state store transactions fail."""
