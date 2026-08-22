"""Service registry exposing all central singletons.
"""

from __future__ import annotations

from typing import Any, Dict


class ServiceRegistry:
    """Maintains singletons of loaded subsystems and platform engines."""

    _instance = None

    def __new__(cls) -> ServiceRegistry:
        if cls._instance is None:
            cls._instance = super(ServiceRegistry, cls).__new__(cls)
            cls._instance._registry = {}
        return cls._instance

    def register_service(self, name: str, service: Any) -> None:
        self._registry[name] = service

    def get_service(self, name: str) -> Any:
        return self._registry.get(name)

    def clear(self) -> None:
        self._registry.clear()
