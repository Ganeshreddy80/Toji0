"""Abstract contracts for the Configuration Manager.
"""

from __future__ import annotations

import abc
from typing import Dict, Any, List, Optional
from research_platform.configuration.models import ConfigurationEntry


class IConfigurationRepository(abc.ABC):
    """Abstract contract for persisting configurations states."""

    @abc.abstractmethod
    def save_entry(self, entry: ConfigurationEntry) -> None:
        """Persist config entry logs."""

    @abc.abstractmethod
    def get_entry(self, config_id: str) -> Optional[ConfigurationEntry]:
        """Retrieve config entry details by ID."""

    @abc.abstractmethod
    def list_entries(self, scope: Optional[str] = None) -> List[ConfigurationEntry]:
        """List active configurations matching filter scope."""


class IConfigurationEngine(abc.ABC):
    """Abstract contract for configuration engines."""

    @abc.abstractmethod
    def update_config(self, scope: str, params: Dict[str, Any]) -> ConfigurationEntry:
        """Update configurations parameters, validating parameters layouts."""


class IValidator(abc.ABC):
    """Abstract contract for validating configurations shapes."""

    @abc.abstractmethod
    def validate(self, scope: str, params: Dict[str, Any]) -> None:
        """Validate config parameters details against required schema formats."""


class IHotReload(abc.ABC):
    """Abstract contract for hot reload execution managers."""

    @abc.abstractmethod
    def reload_configurations(self) -> None:
        """Reload configuration states without resetting runtime loops."""
