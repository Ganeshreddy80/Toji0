"""Generic registry implementation.

``BaseRegistry[T]`` provides a complete, reusable implementation
of ``IRegistry[T]``.  Domain registries subclass it and override
``_validate_item`` if they need custom validation logic.
"""

from __future__ import annotations

import logging
from typing import TypeVar

from toji_platform.core.errors import (
    DuplicateRegistrationError,
    NotRegisteredError,
    RegistryValidationError,
)
from toji_platform.core.registry.interfaces import IRegistry

T = TypeVar("T")

logger = logging.getLogger(__name__)


class BaseRegistry(IRegistry[T]):
    """Dict-backed generic registry with optional validation hook.

    Args:
        registry_name: Human-readable name for log messages and errors.
    """

    def __init__(self, registry_name: str) -> None:
        self._name = registry_name
        self._items: dict[str, T] = {}

    # ── IRegistry ──────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    def register(self, key: str, item: T) -> None:
        if key in self._items:
            raise DuplicateRegistrationError(key, self._name)
        self.validate(key, item)
        self._items[key] = item
        logger.info("[%s] Registered '%s'", self._name, key)

    def unregister(self, key: str) -> T:
        if key not in self._items:
            raise NotRegisteredError(key, self._name)
        item = self._items.pop(key)
        logger.info("[%s] Unregistered '%s'", self._name, key)
        return item

    def get(self, key: str) -> T:
        if key not in self._items:
            raise NotRegisteredError(key, self._name)
        return self._items[key]

    def discover(self, **criteria: object) -> list[T]:
        """Return all items (filter hooks can be overridden by subclasses)."""
        if not criteria:
            return list(self._items.values())
        return self._filter(criteria)

    def list_all(self) -> dict[str, T]:
        return dict(self._items)

    def validate(self, key: str, item: T) -> bool:
        """Run the subclass validation hook.

        The default hook (``_validate_item``) always passes.
        """
        self._validate_item(key, item)
        return True

    def has(self, key: str) -> bool:
        return key in self._items

    def count(self) -> int:
        return len(self._items)

    # ── Extension points ───────────────────────────────────────────────

    def _validate_item(self, key: str, item: T) -> None:
        """Override in subclasses to add domain-specific validation.

        Raise ``RegistryValidationError`` on failure.
        """

    def _filter(self, criteria: dict[str, object]) -> list[T]:
        """Override in subclasses for domain-specific discovery.

        Default: attribute-match filter on each item.
        """
        results: list[T] = []
        for item in self._items.values():
            if all(
                getattr(item, k, None) == v for k, v in criteria.items()
            ):
                results.append(item)
        return results
