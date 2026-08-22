"""Abstract interface for the dependency injection container."""

from __future__ import annotations

import abc
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class IContainer(abc.ABC):
    """Contract for a service container (dependency injection)."""

    @abc.abstractmethod
    def register(
        self,
        service_type: type[T] | str,
        instance: T | None = None,
        factory: Callable[[], T] | None = None,
        *,
        singleton: bool = True,
    ) -> None:
        """Register a service.

        Provide either *instance* (eager singleton) or *factory*
        (lazy creation).  When *singleton* is ``True`` and a *factory*
        is given, the factory is called at most once and the result
        is cached.

        Raises:
            DuplicateServiceError: if the key is already registered.
        """

    @abc.abstractmethod
    def resolve(self, service_type: type[T] | str) -> T:
        """Retrieve a registered service.

        Raises:
            ServiceNotFoundError: if not registered.
        """

    @abc.abstractmethod
    def has(self, service_type: type[Any] | str) -> bool:
        """Return ``True`` if the service is registered."""

    @abc.abstractmethod
    def reset(self) -> None:
        """Remove all registrations."""
