"""Abstract contracts for the Institutional Memory Platform.
"""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Dict, List, Optional

from research_platform.institutional_memory.models import (
    LessonLearnedRecord,
    MemoryMetadata,
    Relationship,
    ReplaySnapshot,
    TradeMemory
)


class IInstitutionalMemoryRepository(abc.ABC):
    """Abstract contract for logging versioned memories."""

    @abc.abstractmethod
    def save_memory(self, category: str, record: Any) -> None:
        """Persist memory log under domain type."""

    @abc.abstractmethod
    def save_relationship(self, rel: Relationship) -> None:
        """Link metadata parents and children."""

    @abc.abstractmethod
    def get_memories_at_timestamp(self, ts: datetime) -> Dict[str, List[Any]]:
        """Query memory log history before timestamp."""


class IDeterministicReplayEngine(abc.ABC):
    """Abstract contract for historical context state replay."""

    @abc.abstractmethod
    def reconstruct_state(self, ts: datetime) -> ReplaySnapshot:
        """Query database memory tables and reconstruct system parameters."""


class IMemorySearchEngine(abc.ABC):
    """Abstract contract for semantic and structured memory querying."""

    @abc.abstractmethod
    def search_memories(self, query_str: str, filters: Dict[str, Any]) -> List[Any]:
        """Perform semantic and structured retrieval."""
class IInstitutionalMemoryOrchestrator(abc.ABC):
    """Abstract contract for institutional memory orchestrator."""
    pass
