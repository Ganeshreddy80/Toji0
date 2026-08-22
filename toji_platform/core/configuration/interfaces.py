"""Abstract interface for configuration providers."""

from __future__ import annotations

import abc
from typing import Any

from toji_platform.core.types import Profile


class IConfigProvider(abc.ABC):
    """Contract for a configuration source."""

    @property
    @abc.abstractmethod
    def profile(self) -> Profile:
        """Active runtime profile."""

    @abc.abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, or *default* if absent."""

    @abc.abstractmethod
    def get_required(self, key: str) -> Any:
        """Return the value for *key*.

        Raises:
            MissingConfigError: if *key* is absent.
        """

    @abc.abstractmethod
    def get_section(self, prefix: str) -> dict[str, Any]:
        """Return all keys that start with *prefix* as a flat dict.

        Example::

            get_section("database")
            # {"database.host": "...", "database.port": "..."}
        """

    @abc.abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Programmatically override a config value."""

    @abc.abstractmethod
    def validate(self, required_keys: list[str]) -> None:
        """Ensure all *required_keys* are present.

        Raises:
            ConfigurationError: with details on missing keys.
        """

    @abc.abstractmethod
    def all(self) -> dict[str, Any]:
        """Return all configuration key-value pairs."""
