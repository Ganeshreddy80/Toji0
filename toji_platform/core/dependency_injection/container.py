"""Dependency injection container implementation.

``Container`` is a lightweight DI container that supports:

* **Eager singletons** — register with a pre-built instance.
* **Lazy singletons** — register with a factory; built on first resolve.
* **Transient factories** — register with ``singleton=False`` to get
  a new instance on every ``resolve`` call.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar

from toji_platform.core.dependency_injection.interfaces import IContainer
from toji_platform.core.errors import DuplicateServiceError, ServiceNotFoundError

T = TypeVar("T")
logger = logging.getLogger(__name__)


@dataclass
class _Registration:
    """Internal bookkeeping for a registered service."""

    instance: Any | None = None
    factory: Callable[[], Any] | None = None
    singleton: bool = True
    _resolved: bool = field(default=False, init=False)


class Container(IContainer):
    """Dict-backed dependency injection container."""

    def __init__(self) -> None:
        self._services: dict[str, _Registration] = {}
        self._lock = threading.RLock()

    # ── helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _key(service_type: type[Any] | str) -> str:
        if isinstance(service_type, str):
            return service_type
        return f"{service_type.__module__}.{service_type.__qualname__}"

    # ── IContainer ─────────────────────────────────────────────────────

    def register(
        self,
        service_type: type[T] | str,
        instance: T | None = None,
        factory: Callable[[], T] | None = None,
        *,
        singleton: bool = True,
    ) -> None:
        key = self._key(service_type)
        with self._lock:
            if key in self._services:
                raise DuplicateServiceError(service_type)

            if instance is not None:
                reg = _Registration(instance=instance, singleton=True)
                reg._resolved = True
            elif factory is not None:
                reg = _Registration(factory=factory, singleton=singleton)
            else:
                raise ValueError(
                    "Must provide either 'instance' or 'factory'"
                )

            self._services[key] = reg
        logger.debug("Container: registered '%s'", key)

    def resolve(self, service_type: type[T] | str) -> T:
        key = self._key(service_type)
        with self._lock:
            reg = self._services.get(key)
            if reg is None:
                raise ServiceNotFoundError(service_type)

            # Eager singleton (instance provided at registration)
            if reg.instance is not None and reg._resolved:
                return reg.instance  # type: ignore[return-value]

            # Lazy singleton — build once, cache
            if reg.factory is not None and reg.singleton and not reg._resolved:
                reg.instance = reg.factory()
                reg._resolved = True
                return reg.instance  # type: ignore[return-value]

            # Transient — new instance every time
            if reg.factory is not None and not reg.singleton:
                return reg.factory()  # type: ignore[return-value]

        raise ServiceNotFoundError(service_type)

    def has(self, service_type: type[Any] | str) -> bool:
        with self._lock:
            return self._key(service_type) in self._services

    def get(self, service_type: type[Any] | str) -> Any:
        try:
            return self.resolve(service_type)
        except Exception:
            return None

    def reset(self) -> None:
        with self._lock:
            self._services.clear()
        logger.debug("Container: reset — all services cleared")
