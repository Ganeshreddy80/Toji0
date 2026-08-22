"""Continuous Runtime loop, engine, and orchestrator interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class IRuntimeLoop(ABC):
    """Abstract base class representing a single subsystem execution loop."""

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> None:
        """Run loop logic within the provided runtime context."""
        pass

    @abstractmethod
    def recover(self, exception: Exception) -> bool:
        """Attempt to recover from a loop exception. Return True if recovered."""
        pass


class IRuntimeEngine(ABC):
    """Core runtime engine running continuous execution loops."""

    @abstractmethod
    def start(self) -> None:
        """Start background execution loops thread."""
        pass

    @abstractmethod
    def pause(self) -> None:
        """Pause execution loops."""
        pass

    @abstractmethod
    def resume(self) -> None:
        """Resume execution loops."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop background execution loops thread."""
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Retrieve current engine state status and loop metrics."""
        pass


class IRuntimeOrchestrator(ABC):
    """Orchestrates continuous engine runs from the container."""

    @abstractmethod
    def boot(self) -> None:
        """Start the continuous runtime engine."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Stop the continuous runtime engine."""
        pass
