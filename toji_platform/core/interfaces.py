"""Top-level kernel interfaces.

``IModule`` and ``IBootable`` define the contracts that every
component plugging into the Toji kernel must satisfy.
"""

from __future__ import annotations

import abc

from toji_platform.core.types import HealthStatus, ModuleId, ModuleState


class IModule(abc.ABC):
    """Contract for any module that the kernel can manage."""

    @property
    @abc.abstractmethod
    def module_id(self) -> ModuleId:
        """Unique identifier for this module."""

    @property
    @abc.abstractmethod
    def state(self) -> ModuleState:
        """Current lifecycle state."""

    @abc.abstractmethod
    def initialize(self) -> None:
        """Perform one-time setup (called by the kernel)."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Release resources (called by the kernel)."""

    @abc.abstractmethod
    def health_check(self) -> HealthStatus:
        """Return the module's current health."""


class IBootable(abc.ABC):
    """Marker interface for components that participate in boot."""

    @abc.abstractmethod
    def boot(self) -> None:
        """Execute the boot sequence for this component."""
