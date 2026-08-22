"""Abstract interface for structured logging."""

from __future__ import annotations

import abc
from typing import Any


class IStructuredLogger(abc.ABC):
    """Contract for a structured logger.

    All logging methods accept arbitrary ``**context`` keyword
    arguments that are included in the structured log output.
    """

    @abc.abstractmethod
    def debug(self, message: str, **context: Any) -> None:
        """Log at DEBUG level."""

    @abc.abstractmethod
    def info(self, message: str, **context: Any) -> None:
        """Log at INFO level."""

    @abc.abstractmethod
    def warning(self, message: str, **context: Any) -> None:
        """Log at WARNING level."""

    @abc.abstractmethod
    def error(self, message: str, **context: Any) -> None:
        """Log at ERROR level."""

    @abc.abstractmethod
    def critical(self, message: str, **context: Any) -> None:
        """Log at CRITICAL level."""
