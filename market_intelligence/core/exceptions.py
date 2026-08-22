"""Subsystem specific exceptions for the Market Intelligence Layer."""

from __future__ import annotations


class MarketIntelligenceException(Exception):
    """Base exception class for all MIL errors."""


class StateValidationError(MarketIntelligenceException):
    """Raised when validation of market state models fails."""


class RepositoryException(MarketIntelligenceException):
    """Raised when repository snapshot loading, saving, or indexing fails."""


class PluginInitializationError(MarketIntelligenceException):
    """Raised when MIL plugin initialization or boot checks fail."""


class StateStoreError(MarketIntelligenceException):
    """Raised when thread-safe state store operations encounter issues."""


class ReplayDivergenceError(MarketIntelligenceException):
    """Raised when replay verification detects state divergence."""


class OrchestratorError(MarketIntelligenceException):
    """Raised when orchestrator encounters coordination or execution failures."""


class HealthCheckError(MarketIntelligenceException):
    """Raised when health monitoring detects critical failures."""
