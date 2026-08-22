"""Exceptions for the Backtesting Engine (Sprint 7A)."""

from __future__ import annotations


class BacktestingException(Exception):
    """Base exception for all Backtesting Engine errors."""


class ReplayError(BacktestingException):
    """Raised when historical bar replay encounters state or timestamp errors."""


class SimulatedBrokerError(BacktestingException):
    """Raised when simulated order validation or broker state transition fails."""


class OrderMatchingError(BacktestingException):
    """Raised when order matching encounters invalid prices or configurations."""


class TradeLedgerError(BacktestingException):
    """Raised when position tracking or PnL accounting fails validation."""


class EquityEngineError(BacktestingException):
    """Raised when equity calculation or drawdown tracking encounters invalid inputs."""


class BacktestRepositoryError(BacktestingException):
    """Raised when persistence or retrieval of backtest entities fails."""


class BacktestOrchestratorError(BacktestingException):
    """Raised when the backtest orchestrator pipeline encounters an error."""


class WalkForwardValidationError(BacktestingException):
    """Raised when walk-forward validation parameters, windows, or dataset validation fails."""

