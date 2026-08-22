"""Strategy registry."""

from __future__ import annotations
from toji_platform.strategy_engine.base import IStrategy

class StrategyRegistry:
    """Manages active strategy plugins and prevents duplicate registrations."""

    def __init__(self) -> None:
        self._strategies: dict[str, IStrategy] = {}

    def register(self, strategy: IStrategy) -> None:
        """Register a strategy, raising ValueError on duplicate registrations."""
        meta = strategy.metadata()
        if meta.name in self._strategies:
            raise ValueError(f"Strategy '{meta.name}' is already registered.")
        self._strategies[meta.name] = strategy

    def unregister(self, name: str) -> IStrategy | None:
        """Unregister a strategy by name."""
        return self._strategies.pop(name, None)

    def get(self, name: str) -> IStrategy | None:
        """Fetch a registered strategy by name."""
        return self._strategies.get(name)

    def list_strategies(self) -> list[IStrategy]:
        """List all currently registered strategies."""
        return list(self._strategies.values())

    def clear(self) -> None:
        """Clear all registered strategies."""
        self._strategies.clear()
