"""Session manager tracking active paper lifecycles.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from research_platform.paper_trading.models import PaperAccount, PaperExecutionSession

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages paper trading start/stop state phases."""

    def start_session(self, account: PaperAccount) -> PaperExecutionSession:
        session = PaperExecutionSession(
            session_id=f"psess-{uuid.uuid4().hex[:8]}",
            start_time=datetime.now(timezone.utc),
            status="ACTIVE",
            account=account
        )
        logger.info("Paper session '%s' initialized with balance %.2f", session.session_id, account.cash)
        return session

    def stop_session(self, session: PaperExecutionSession) -> PaperExecutionSession:
        return session.model_copy(update={
            "status": "INACTIVE",
            "end_time": datetime.now(timezone.utc)
        })
