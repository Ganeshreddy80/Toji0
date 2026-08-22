"""Paper Trading Session Lifecycle Manager (Sprint 9A)."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import uuid
from typing import Optional

from paper_trading.events import PaperSessionStarted, PaperSessionStopped
from paper_trading.models.paper_models import (
    PaperAccount,
    PaperSession,
    PaperSessionStatus,
)
from paper_trading.repository import PaperRepository
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class PaperSessionManager:
    """Manages paper trading session lifecycle and state transitions."""

    def __init__(
        self,
        repository: Optional[PaperRepository] = None,
        event_bus: Optional[IEventBus] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._repository = repository or PaperRepository()
        self._event_bus = event_bus
        self._session: Optional[PaperSession] = None

    def start_session(
        self,
        account: PaperAccount,
        session_id: Optional[str] = None,
    ) -> PaperSession:
        """Start a new paper trading session.

        Transitions: STOPPED -> STARTING -> RUNNING.
        """
        with self._lock:
            if self._session and self._session.status in (PaperSessionStatus.RUNNING, PaperSessionStatus.STARTING):
                raise ValueError(f"Session {self._session.session_id} is already active in state {self._session.status}.")

            sid = session_id or str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            # Transition: STARTING
            starting_session = PaperSession(
                session_id=sid,
                started_at=now,
                status=PaperSessionStatus.STARTING,
                account=account,
            )
            self._session = starting_session
            self._repository.save_session(starting_session)

            # Transition: RUNNING
            running_session = PaperSession(
                session_id=sid,
                started_at=now,
                status=PaperSessionStatus.RUNNING,
                account=account,
            )
            self._session = running_session
            self._repository.save_session(running_session)

            if self._event_bus:
                self._event_bus.publish(PaperSessionStarted(session=running_session))

            return running_session

    def stop_session(self) -> PaperSession:
        """Stop active paper trading session.

        Transitions: RUNNING -> STOPPING -> STOPPED.
        """
        with self._lock:
            if not self._session or self._session.status == PaperSessionStatus.STOPPED:
                if self._session:
                    return self._session
                raise ValueError("No active session to stop.")

            sid = self._session.session_id
            start_time = self._session.started_at
            account = self._session.account

            # Transition: STOPPING
            stopping_session = PaperSession(
                session_id=sid,
                started_at=start_time,
                status=PaperSessionStatus.STOPPING,
                account=account,
            )
            self._session = stopping_session
            self._repository.save_session(stopping_session)

            # Transition: STOPPED
            stopped_session = PaperSession(
                session_id=sid,
                started_at=start_time,
                status=PaperSessionStatus.STOPPED,
                account=account,
            )
            self._session = stopped_session
            self._repository.save_session(stopped_session)

            if self._event_bus:
                self._event_bus.publish(PaperSessionStopped(session=stopped_session))

            return stopped_session

    def set_error_state(self, error_message: str) -> PaperSession:
        """Transition session to ERROR state."""
        with self._lock:
            if not self._session:
                raise ValueError("No active session to set to ERROR state.")

            error_session = PaperSession(
                session_id=self._session.session_id,
                started_at=self._session.started_at,
                status=PaperSessionStatus.ERROR,
                account=self._session.account,
            )
            self._session = error_session
            self._repository.save_session(error_session)
            return error_session

    def get_current_session(self) -> Optional[PaperSession]:
        """Get current active session."""
        with self._lock:
            return self._session
