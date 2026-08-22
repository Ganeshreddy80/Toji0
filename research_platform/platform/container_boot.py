"""Container bootloader registering core container scopes.
"""

from __future__ import annotations

from toji_platform.core.dependency_injection import Container


class ContainerBootloader:
    """Configures the platform dependency injection container."""

    def boot_container(self) -> Container:
        container = Container()
        return container
