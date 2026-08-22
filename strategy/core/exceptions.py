"""Exceptions for the Strategy Subsystem."""

from __future__ import annotations


class StrategyException(Exception):
    """Base exception for all strategy-related issues."""


class StateStoreError(StrategyException):
    """Exception raised by the StrategyStateStore."""


class RepositoryError(StrategyException):
    """Exception raised by the StrategyRepository."""


class OrchestratorError(StrategyException):
    """Exception raised by the StrategyOrchestrator."""


class StrategyEngineError(StrategyException):
    """Exception raised by the StrategyEngine or sub-strategies."""
