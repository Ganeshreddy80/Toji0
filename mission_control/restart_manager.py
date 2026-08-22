"""Thread-safe Service Restart Manager & Loop Prevention Engine for Mission Control (Sprint 10C)."""

from __future__ import annotations

import collections
from datetime import datetime, timedelta, timezone
import logging
import threading
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from mission_control.policies import AutoRestartPolicy

logger = logging.getLogger(__name__)


class RestartRecord(BaseModel):
    """Immutable record of a service restart execution."""

    service_name: str = Field(..., description="Target service identifier.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Restart timestamp.",
    )
    is_manual: bool = Field(default=False, description="Whether restart was manually triggered.")
    operator: str = Field(default="SYSTEM", description="Requesting entity.")
    reason: str = Field(..., description="Restart justification.")

    model_config = ConfigDict(frozen=True)


class RestartManager:
    """Thread-safe Restart Manager tracking restart history and enforcing loop prevention limits."""

    def __init__(
        self,
        policy: Optional[AutoRestartPolicy] = None,
        max_history: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._policy = policy or AutoRestartPolicy()
        self._history: collections.deque[RestartRecord] = collections.deque(maxlen=max_history)
        self._service_restarts: Dict[str, List[datetime]] = collections.defaultdict(list)

    def set_policy(self, policy: AutoRestartPolicy) -> None:
        """Update auto restart policy."""
        with self._lock:
            self._policy = policy

    def can_restart(self, service_name: str) -> Tuple[bool, str]:
        """Check whether service is permitted to restart under loop-prevention limits."""
        with self._lock:
            if not self._policy.enabled:
                return False, "Auto-restart policy is disabled"

            timestamps = self._service_restarts[service_name]
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=self._policy.window_seconds)
            recent_restarts = [t for t in timestamps if t > cutoff]
            self._service_restarts[service_name] = recent_restarts

            if len(recent_restarts) >= self._policy.max_restarts:
                return False, f"Restart limit exceeded ({len(recent_restarts)}/{self._policy.max_restarts} in {self._policy.window_seconds}s)"

            return True, "Permitted"

    def request_restart(
        self,
        service_name: str,
        reason: str,
        operator: str = "SYSTEM",
    ) -> Tuple[bool, Optional[RestartRecord], str]:
        """Execute an automatic restart request if loop-prevention checks pass.

        Returns (success: bool, record: Optional[RestartRecord], message: str).
        """
        with self._lock:
            allowed, msg = self.can_restart(service_name)
            if not allowed:
                logger.warning("Restart REJECTED for '%s': %s", service_name, msg)
                return False, None, msg

            record = RestartRecord(
                service_name=service_name,
                timestamp=datetime.now(timezone.utc),
                is_manual=False,
                operator=operator,
                reason=reason,
            )
            self._history.append(record)
            self._service_restarts[service_name].append(record.timestamp)
            logger.info("Auto-restart EXECUTED for '%s': %s", service_name, reason)
            return True, record, "Restart executed successfully"

    def force_restart(
        self,
        service_name: str,
        reason: str,
        operator: str = "OPERATOR",
    ) -> RestartRecord:
        """Force a manual restart bypassing loop-prevention checks."""
        with self._lock:
            record = RestartRecord(
                service_name=service_name,
                timestamp=datetime.now(timezone.utc),
                is_manual=True,
                operator=operator,
                reason=reason,
            )
            self._history.append(record)
            self._service_restarts[service_name].append(record.timestamp)
            logger.info("Manual force-restart EXECUTED for '%s' by %s: %s", service_name, operator, reason)
            return record

    def get_restart_history(
        self,
        service_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RestartRecord]:
        """Query restart history."""
        with self._lock:
            filtered = [r for r in self._history if not service_name or r.service_name == service_name]
            return filtered[-limit:] if limit else filtered

    def get_restart_count(self, service_name: str, window_seconds: Optional[float] = None) -> int:
        """Get restart count for a service in given window."""
        with self._lock:
            win = window_seconds or self._policy.window_seconds
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=win)
            return sum(1 for t in self._service_restarts[service_name] if t > cutoff)

    def clear(self) -> None:
        """Clear restart history and counters."""
        with self._lock:
            self._history.clear()
            self._service_restarts.clear()
