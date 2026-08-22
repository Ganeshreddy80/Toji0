"""Database repository persisting append-only versioned logs.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List

from research_platform.institutional_memory.interfaces import IInstitutionalMemoryRepository
from research_platform.institutional_memory.models import Relationship


class InstitutionalMemoryRepository(IInstitutionalMemoryRepository):
    """Memory database repository for TOJI Institutional Knowledge."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._db: Dict[str, List[Any]] = {
            "trades": [],
            "positions": [],
            "strategies": [],
            "research": [],
            "risks": [],
            "observability": [],
            "ai": [],
            "human": []
        }
        self._relationships: List[Relationship] = []

    def save_memory(self, category: str, record: Any) -> None:
        """Persist memory log under domain type."""
        with self._lock:
            if category not in self._db:
                self._db[category] = []
            self._db[category].append(record)

    def save_relationship(self, rel: Relationship) -> None:
        """Link metadata parents and children."""
        with self._lock:
            self._relationships.append(rel)

    def get_memories_at_timestamp(self, ts: datetime) -> Dict[str, List[Any]]:
        """Query memory log history before timestamp."""
        with self._lock:
            filtered: Dict[str, List[Any]] = {}
            for cat, records in self._db.items():
                filtered[cat] = []
                for rec in records:
                    created = getattr(getattr(rec, "metadata", None), "created_at", None)
                    if created and created <= ts:
                        filtered[cat].append(rec)
            return filtered

    def list_memories_by_category(self, category: str) -> List[Any]:
        with self._lock:
            return list(self._db.get(category, []))

    def list_relationships(self) -> List[Relationship]:
        with self._lock:
            return list(self._relationships)
