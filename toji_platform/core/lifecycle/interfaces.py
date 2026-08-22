"""Abstract interfaces for lifecycle management."""

from __future__ import annotations

import abc

from toji_platform.core.types import HealthStatus


class ILifecycle(abc.ABC):
    """Contract for a component with managed startup / shutdown."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable component name."""

    @abc.abstractmethod
    def start(self) -> None:
        """Initialise and start the component."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Gracefully stop and release resources."""


class IHealthCheck(abc.ABC):
    """Contract for components that report health status."""

    @abc.abstractmethod
    def check_health(self) -> HealthStatus:
        """Return current health status."""
