"""Memory tracking rolling cache with sliding retention windows.
"""

from __future__ import annotations

from typing import Any, Dict, List

from research_platform.ai_intelligence.interfaces import IAIMemory


class AIMemory(IAIMemory):
    """Retains recent drawdowns, risk alerts, and trade fills."""

    def __init__(self, retention_limit: int = 10) -> None:
        self.retention_limit = retention_limit
        self._memory: Dict[str, List[Any]] = {}

    def record_event(self, key: str, value: Any) -> None:
        """Record trade event or alert log."""
        if key not in self._memory:
            self._memory[key] = []
        
        self._memory[key].append(value)
        # Limit size
        if len(self._memory[key]) > self.retention_limit:
            self._memory[key].pop(0)

    def get_events(self, key: str) -> List[Any]:
        return list(self._memory.get(key, []))
