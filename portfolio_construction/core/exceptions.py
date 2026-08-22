"""Exceptions for the Portfolio Construction Engine."""

from __future__ import annotations


class PortfolioConstructionException(Exception):
    """Base exception for Portfolio Construction Engine errors."""

    pass


class ConstraintViolationError(PortfolioConstructionException):
    """Raised when portfolio constraints are violated."""

    pass


class OptimizationError(PortfolioConstructionException):
    """Raised when portfolio optimization solver fails."""

    pass


class OrchestratorError(PortfolioConstructionException):
    """Raised when portfolio orchestrator execution encounters unrecoverable setup error."""

    pass
