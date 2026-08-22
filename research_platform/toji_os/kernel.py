"""Kernel engine managing active control sessions.
"""

from __future__ import annotations

from research_platform.toji_os.models import OSSession


class OSKernel:
    """Controls OS kernel state parameters."""

    def initialize_session(self, session_id: str, user_id: str) -> OSSession:
        return OSSession(
            session_id=session_id,
            user_id=user_id,
            active=True
        )
