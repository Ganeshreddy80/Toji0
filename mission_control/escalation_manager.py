"""Thread-safe Escalation Manager for Mission Control Operational Automation (Sprint 10C)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from mission_control.policies import EscalationPolicy

logger = logging.getLogger(__name__)


class EscalationLevel(str, Enum):
    """Incident escalation severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class EscalationReason(str, Enum):
    """Reason classifications for incident escalation."""

    RESTART_LIMIT_EXCEEDED = "RESTART_LIMIT_EXCEEDED"
    REPEATED_FAILURES = "REPEATED_FAILURES"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    RECOVERY_EXHAUSTION = "RECOVERY_EXHAUSTION"
    MANUAL_ESCALATION = "MANUAL_ESCALATION"


class EscalationRecord(BaseModel):
    """Immutable record of an operational incident escalation."""

    escalation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique escalation UUID.",
    )
    service_name: str = Field(..., description="Target service identifier.")
    level: EscalationLevel = Field(..., description="Escalation severity level.")
    reason: EscalationReason = Field(..., description="Escalation reason category.")
    message: str = Field(..., description="Escalation summary description.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Escalation timestamp.",
    )
    details: Optional[Dict[str, str]] = Field(default=None, description="Additional context attributes.")

    model_config = ConfigDict(frozen=True)


class EscalationManager:
    """Thread-safe Incident Escalation Manager tracking escalation events and maintaining escalation history."""

    def __init__(
        self,
        policy: Optional[EscalationPolicy] = None,
        max_history: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._policy = policy or EscalationPolicy()
        self._history: collections.deque[EscalationRecord] = collections.deque(maxlen=max_history)
        self._active_escalations: Dict[str, EscalationRecord] = {}

    def set_policy(self, policy: EscalationPolicy) -> None:
        """Update escalation policy."""
        with self._lock:
            self._policy = policy

    def raise_escalation(
        self,
        service_name: str,
        level: EscalationLevel,
        reason: EscalationReason,
        message: str,
        details: Optional[Dict[str, str]] = None,
    ) -> EscalationRecord:
        """Raise an operational escalation event."""
        with self._lock:
            record = EscalationRecord(
                service_name=service_name,
                level=level,
                reason=reason,
                message=message,
                timestamp=datetime.now(timezone.utc),
                details=details,
            )
            self._history.append(record)
            self._active_escalations[service_name] = record
            logger.error("ESCALATION [%s/%s] for '%s': %s", level.value, reason.value, service_name, message)
            return record

    def escalate_restart_limit_exceeded(self, service_name: str, restart_count: int) -> EscalationRecord:
        """Raise CRITICAL escalation when restart limit is exceeded."""
        return self.raise_escalation(
            service_name=service_name,
            level=EscalationLevel.CRITICAL,
            reason=EscalationReason.RESTART_LIMIT_EXCEEDED,
            message=f"Service '{service_name}' exceeded maximum restart limit ({restart_count} restarts).",
        )

    def escalate_repeated_failures(self, service_name: str, failure_count: int) -> EscalationRecord:
        """Raise ERROR escalation for repeated service failures."""
        return self.raise_escalation(
            service_name=service_name,
            level=EscalationLevel.ERROR,
            reason=EscalationReason.REPEATED_FAILURES,
            message=f"Service '{service_name}' experienced repeated failures ({failure_count} occurrences).",
        )

    def escalate_dependency_failure(self, service_name: str, failed_dependencies: List[str]) -> EscalationRecord:
        """Raise ERROR escalation when upstream dependency fails."""
        return self.raise_escalation(
            service_name=service_name,
            level=EscalationLevel.ERROR,
            reason=EscalationReason.DEPENDENCY_FAILURE,
            message=f"Service '{service_name}' impacted by upstream dependency failures: {', '.join(failed_dependencies)}.",
        )

    def escalate_recovery_exhaustion(self, service_name: str, retry_count: int) -> EscalationRecord:
        """Raise CRITICAL escalation when automated recovery retries are exhausted."""
        return self.raise_escalation(
            service_name=service_name,
            level=EscalationLevel.CRITICAL,
            reason=EscalationReason.RECOVERY_EXHAUSTION,
            message=f"Automated recovery exhausted for service '{service_name}' after {retry_count} retries.",
        )

    def resolve_escalation(self, service_name: str) -> bool:
        """Resolve active escalation for a service."""
        with self._lock:
            if service_name in self._active_escalations:
                del self._active_escalations[service_name]
                logger.info("Escalation RESOLVED for '%s'", service_name)
                return True
            return False

    def get_active_escalations(self) -> List[EscalationRecord]:
        """Get all currently active escalation records."""
        with self._lock:
            return list(self._active_escalations.values())

    def get_escalation_history(
        self,
        service_name: Optional[str] = None,
        level: Optional[EscalationLevel] = None,
        limit: Optional[int] = None,
    ) -> List[EscalationRecord]:
        """Query escalation history with optional filters."""
        with self._lock:
            filtered: List[EscalationRecord] = []
            for record in self._history:
                if service_name and record.service_name != service_name:
                    continue
                if level and record.level != level:
                    continue
                filtered.append(record)
            return filtered[-limit:] if limit else filtered

    def clear(self) -> None:
        """Clear escalation records."""
        with self._lock:
            self._history.clear()
            self._active_escalations.clear()
