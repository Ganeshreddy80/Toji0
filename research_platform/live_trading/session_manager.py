"""Session Manager controlling start/stop loops and calendar holiday checks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from research_platform.live_trading.models import LiveTradingSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages active trading sessions, holidays calendar dates, and shutdowns."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._active = False
        self._holidays: Set[str] = set()  # format: YYYY-MM-DD

    @property
    def is_active(self) -> bool:
        return self._active

    def register_holiday(self, date_str: str) -> None:
        self._holidays.add(date_str)

    def is_market_holiday(self, dt: datetime) -> bool:
        date_str = dt.strftime("%Y-%m-%d")
        return date_str in self._holidays

    def start_session(self) -> LiveTradingSession:
        self._active = True
        logger.info("Live Trading Session %s started.", self.session_id)
        return LiveTradingSession(
            session_id=self.session_id,
            status="ACTIVE",
            start_time=datetime.now(timezone.utc)
        )

    def stop_session(self) -> LiveTradingSession:
        self._active = False
        logger.warning("Live Trading Session %s stopped.", self.session_id)
        return LiveTradingSession(
            session_id=self.session_id,
            status="TERMINATED",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc)
        )
