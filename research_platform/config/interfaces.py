"""R51 Central Configuration Interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from research_platform.config.models import CentralConfig


class IConfigManager(ABC):
    """Abstract contract for configuration retrieval, validation, and override updates."""

    @abstractmethod
    def get_config(self) -> CentralConfig:
        """Retrieve the active configuration root model."""
        pass

    @abstractmethod
    def apply_overrides(self, overrides: Dict[str, Any]) -> None:
        """Apply dynamic configuration updates and run validator checks."""
        pass

    @abstractmethod
    def reload(self) -> None:
        """Hot-reload configuration profile settings from YAML and environment."""
        pass
