"""Abstract interface for typed registries.

``IRegistry[T]`` defines the five standard operations every
registry must support.
"""

from __future__ import annotations

import abc
from typing import Generic, TypeVar

T = TypeVar("T")


class IRegistry(abc.ABC, Generic[T]):
    """Generic registry that stores items keyed by string name.

    Type parameter *T* is the type of the items stored.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name for this registry."""

    @abc.abstractmethod
    def register(self, key: str, item: T) -> None:
        """Add *item* under *key*.

        Raises:
            DuplicateRegistrationError: if *key* already exists.
            RegistryValidationError: if *item* fails validation.
        """

    @abc.abstractmethod
    def unregister(self, key: str) -> T:
        """Remove and return the item at *key*.

        Raises:
            NotRegisteredError: if *key* does not exist.
        """

    @abc.abstractmethod
    def get(self, key: str) -> T:
        """Return the item at *key*.

        Raises:
            NotRegisteredError: if *key* does not exist.
        """

    @abc.abstractmethod
    def discover(self, **criteria: object) -> list[T]:
        """Return items matching arbitrary filter *criteria*.

        Implementations define which criteria keys are supported.
        An empty *criteria* may return all items.
        """

    @abc.abstractmethod
    def list_all(self) -> dict[str, T]:
        """Return a copy of all registered items."""

    @abc.abstractmethod
    def validate(self, key: str, item: T) -> bool:
        """Check whether *item* is valid for this registry.

        Returns ``True`` on success; raises ``RegistryValidationError``
        on failure.
        """

    @abc.abstractmethod
    def has(self, key: str) -> bool:
        """Return ``True`` if *key* is registered."""

    @abc.abstractmethod
    def count(self) -> int:
        """Return the number of registered items."""
