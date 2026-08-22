"""Strategy execution context."""

from __future__ import annotations
from typing import Any

class StrategyContext:
    """Read-only sandbox context exposed to running strategies to prevent direct resource access."""

    def __init__(self, strategy_name: str, config: dict[str, Any]) -> None:
        self.strategy_name = strategy_name
        self._config = config

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Fetch read-only strategy settings dynamically."""
        return self._config.get(key, default)
