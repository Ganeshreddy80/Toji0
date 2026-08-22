"""Chaos scenarios registry."""

from __future__ import annotations
from typing import Any, Callable

class ChaosScenarioRegistry:
    """Registry to keep track of available chaos scenarios."""

    def __init__(self) -> None:
        self._scenarios: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, scenario_fn: Callable[..., Any]) -> None:
        self._scenarios[name] = scenario_fn

    def get(self, name: str) -> Callable[..., Any] | None:
        return self._scenarios.get(name)

    def list_scenarios(self) -> list[str]:
        return list(self._scenarios.keys())

    def clear(self) -> None:
        self._scenarios.clear()

registry = ChaosScenarioRegistry()
