"""Kill Switch implementing emergency trading pause switches.
"""

from __future__ import annotations

from research_platform.risk_management.models import KillSwitchStatus


class KillSwitch:
    """Provides system-wide emergency halt flags and read-only modes."""

    def __init__(self) -> None:
        self._activated = False
        self._reason: Optional[str] = None

    @property
    def is_activated(self) -> bool:
        return self._activated

    def activate(self, reason: str) -> None:
        self._activated = True
        self._reason = reason

    def release(self) -> None:
        self._activated = False
        self._reason = None

    def get_status(self) -> KillSwitchStatus:
        return KillSwitchStatus(
            activated=self._activated,
            reason=self._reason
        )
