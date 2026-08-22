"""Thread-safe Audit Logger for Mission Control Operational Automation (Sprint 10C)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class AuditLogEntry(BaseModel):
    """Immutable audit log record for operational actions."""

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Audit entry timestamp.",
    )
    action: str = Field(..., description="Operational action performed (e.g. RESTART, RECOVERY, ESCALATION).")
    service: str = Field(..., description="Target service identifier.")
    outcome: str = Field(..., description="Execution outcome (SUCCESS, FAILED, SKIPPED, ESCALATED).")
    operator: str = Field(default="SYSTEM", description="Entity requesting/performing action.")
    reason: str = Field(..., description="Justification or context for the action.")

    model_config = ConfigDict(frozen=True)


class AuditLog:
    """Thread-safe Bounded Audit Logger preventing unbounded memory growth."""

    def __init__(self, max_entries: int = 2000) -> None:
        self._lock = threading.RLock()
        self._entries: collections.deque[AuditLogEntry] = collections.deque(maxlen=max_entries)

    def record(
        self,
        action: str,
        service: str,
        outcome: str,
        reason: str,
        operator: str = "SYSTEM",
    ) -> AuditLogEntry:
        """Record an audit log entry."""
        with self._lock:
            entry = AuditLogEntry(
                action=action,
                service=service,
                outcome=outcome,
                operator=operator,
                reason=reason,
            )
            self._entries.append(entry)
            logger.info("AUDIT [%s] %s on '%s': %s (%s)", outcome, action, service, reason, operator)
            return entry

    def get_entries(
        self,
        service: Optional[str] = None,
        action: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditLogEntry]:
        """Query audit log entries with optional filters."""
        with self._lock:
            filtered: List[AuditLogEntry] = []
            for entry in self._entries:
                if service and entry.service != service:
                    continue
                if action and entry.action != action:
                    continue
                filtered.append(entry)
            return filtered[-limit:] if limit else filtered

    def clear(self) -> None:
        """Clear all audit log records."""
        with self._lock:
            self._entries.clear()
