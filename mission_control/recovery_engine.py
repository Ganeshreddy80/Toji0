"""Thread-safe Service & Infrastructure Recovery Engine for Mission Control (Sprint 10C)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import time
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field

from mission_control.policies import RecoveryPolicy

logger = logging.getLogger(__name__)


class RecoveryType(str, Enum):
    """Classification type of automated recovery."""

    SERVICE_RECOVERY = "SERVICE_RECOVERY"
    HEARTBEAT_RECOVERY = "HEARTBEAT_RECOVERY"
    DEGRADED_RECOVERY = "DEGRADED_RECOVERY"
    REPEATED_FAILURE_RECOVERY = "REPEATED_FAILURE_RECOVERY"


class RecoveryAttemptRecord(BaseModel):
    """Immutable record of an automated recovery attempt."""

    service_name: str = Field(..., description="Target service identifier.")
    recovery_type: RecoveryType = Field(..., description="Recovery classification type.")
    attempt_number: int = Field(..., ge=1, description="Sequential attempt count.")
    success: bool = Field(..., description="Whether attempt succeeded.")
    message: str = Field(..., description="Recovery attempt result message.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Attempt timestamp.",
    )

    model_config = ConfigDict(frozen=True)


class RecoveryEngine:
    """Thread-safe Recovery Engine processing automated service recovery logic under strict SLAs (<100ms decision)."""

    def __init__(
        self,
        policy: Optional[RecoveryPolicy] = None,
        max_history: int = 1000,
    ) -> None:
        self._lock = threading.RLock()
        self._policy = policy or RecoveryPolicy()
        self._attempts_count: Dict[str, int] = collections.defaultdict(int)
        self._history: collections.deque[RecoveryAttemptRecord] = collections.deque(maxlen=max_history)

    def set_policy(self, policy: RecoveryPolicy) -> None:
        """Update recovery policy."""
        with self._lock:
            self._policy = policy

    def can_attempt_recovery(self, service_name: str) -> Tuple[bool, str]:
        """Check whether recovery attempt is permitted under retry limit rules.

        Executes under 100ms decision SLA.
        """
        start_t = time.perf_counter()
        with self._lock:
            if not self._policy.enabled:
                return False, "Recovery policy is disabled"

            attempts = self._attempts_count[service_name]
            if attempts >= self._policy.max_retries:
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0
                return False, f"Recovery retries exhausted ({attempts}/{self._policy.max_retries})"

            elapsed_ms = (time.perf_counter() - start_t) * 1000.0
            return True, f"Permitted (attempt {attempts + 1}/{self._policy.max_retries})"

    def execute_service_recovery(
        self,
        service_name: str,
        reason: str,
    ) -> Tuple[bool, RecoveryAttemptRecord, str]:
        """Execute automated service recovery for an UNHEALTHY or failed service."""
        return self._run_recovery(service_name, RecoveryType.SERVICE_RECOVERY, reason)

    def execute_heartbeat_recovery(
        self,
        service_name: str,
        latency_ms: float,
    ) -> Tuple[bool, RecoveryAttemptRecord, str]:
        """Execute automated recovery for a heartbeat failure / timeout."""
        reason = f"Heartbeat latency excessive ({latency_ms:.1f} ms)"
        return self._run_recovery(service_name, RecoveryType.HEARTBEAT_RECOVERY, reason)

    def execute_degraded_recovery(
        self,
        service_name: str,
        reason: str,
    ) -> Tuple[bool, RecoveryAttemptRecord, str]:
        """Execute automated recovery for a DEGRADED service."""
        with self._lock:
            if not self._policy.auto_recover_degraded:
                rec = RecoveryAttemptRecord(
                    service_name=service_name,
                    recovery_type=RecoveryType.DEGRADED_RECOVERY,
                    attempt_number=max(1, self._attempts_count[service_name]),
                    success=False,
                    message="Degraded recovery disabled by policy",
                )
                return False, rec, "Degraded recovery disabled by policy"

        return self._run_recovery(service_name, RecoveryType.DEGRADED_RECOVERY, reason)

    def execute_repeated_failure_recovery(
        self,
        service_name: str,
        failure_count: int,
    ) -> Tuple[bool, RecoveryAttemptRecord, str]:
        """Execute automated recovery for repeated service failures."""
        reason = f"Repeated failure threshold reached ({failure_count} occurrences)"
        return self._run_recovery(service_name, RecoveryType.REPEATED_FAILURE_RECOVERY, reason)

    def reset_recovery_attempts(self, service_name: str) -> None:
        """Reset attempt counter for a recovered service."""
        with self._lock:
            self._attempts_count[service_name] = 0
            logger.info("Reset recovery attempts for '%s'", service_name)

    def get_recovery_history(
        self,
        service_name: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[RecoveryAttemptRecord]:
        """Query recovery history."""
        with self._lock:
            filtered = [r for r in self._history if not service_name or r.service_name == service_name]
            return filtered[-limit:] if limit else filtered

    def get_attempt_count(self, service_name: str) -> int:
        """Get current recovery attempt count for a service."""
        with self._lock:
            return self._attempts_count[service_name]

    def clear(self) -> None:
        """Clear recovery history and attempt counters."""
        with self._lock:
            self._attempts_count.clear()
            self._history.clear()

    def _run_recovery(
        self,
        service_name: str,
        recovery_type: RecoveryType,
        reason: str,
    ) -> Tuple[bool, RecoveryAttemptRecord, str]:
        """Internal recovery execution handler."""
        with self._lock:
            can, msg = self.can_attempt_recovery(service_name)
            if not can:
                rec = RecoveryAttemptRecord(
                    service_name=service_name,
                    recovery_type=recovery_type,
                    attempt_number=self._attempts_count[service_name],
                    success=False,
                    message=msg,
                )
                self._history.append(rec)
                return False, rec, msg

            self._attempts_count[service_name] += 1
            attempt_num = self._attempts_count[service_name]

            # In infrastructure simulation, recovery execution succeeds when attempted within retry limit
            success = True
            succ_msg = f"Recovery attempt {attempt_num} succeeded: {reason}"

            record = RecoveryAttemptRecord(
                service_name=service_name,
                recovery_type=recovery_type,
                attempt_number=attempt_num,
                success=success,
                message=succ_msg,
            )
            self._history.append(record)
            logger.info("Recovery EXECUTED [%s] for '%s' (attempt %d)", recovery_type.value, service_name, attempt_num)
            return True, record, succ_msg
