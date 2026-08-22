"""Thread-safe Bounded In-Memory Audit Logger (Sprint 12C)."""

from __future__ import annotations

import collections
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class AuditEntry(BaseModel):
    """Immutable record of an operational action or governance event."""

    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: str = Field(..., description="Action performed (e.g. DEPLOYMENT_CREATED).")
    actor: str = Field(default="system", description="Initiator of action.")
    resource_type: str = Field(..., description="Target resource category.")
    resource_id: str = Field(..., description="Target resource identifier.")
    details: Dict[str, Any] = Field(default_factory=dict, description="Contextual payload metadata.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class AuditLogger:
    """Thread-safe in-memory Audit Logger maintaining a bounded entry log without filesystem persistence."""

    def __init__(self, max_entries: int = 5000) -> None:
        self._lock = threading.RLock()
        self._max_entries = max_entries
        # Bounded deque of AuditEntry
        self._entries: collections.deque = collections.deque(maxlen=self._max_entries)

    def record_entry(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        actor: str = "system",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Record an immutable audit entry."""
        with self._lock:
            entry = AuditEntry(
                action=action,
                actor=actor,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or {},
            )
            self._entries.append(entry)
            logger.info("Recorded audit entry [%s] by '%s' on %s/%s", action, actor, resource_type, resource_id)
            return entry

    def get_entries(
        self,
        action: Optional[str] = None,
        actor: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> List[AuditEntry]:
        """Query and filter stored audit log entries."""
        with self._lock:
            results: List[AuditEntry] = []
            for e in self._entries:
                if action and e.action != action:
                    continue
                if actor and e.actor != actor:
                    continue
                if resource_type and e.resource_type != resource_type:
                    continue
                if resource_id and e.resource_id != resource_id:
                    continue
                results.append(e)
            return results

    def count(self) -> int:
        """Return total count of recorded audit entries."""
        with self._lock:
            return len(self._entries)

    def clear(self) -> None:
        """Clear all audit entries."""
        with self._lock:
            self._entries.clear()
