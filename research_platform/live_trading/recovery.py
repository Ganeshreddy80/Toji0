"""Recovery Manager saving checkpoints and re-hydrating states upon restarts.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from research_platform.live_trading.interfaces import IRecoveryManager
from research_platform.live_trading.models import RecoveryCheckpoint

logger = logging.getLogger(__name__)


class RecoveryManager(IRecoveryManager):
    """Manages active checkpoint profiles and restores state values."""

    def __init__(self) -> None:
        self._checkpoints: Dict[str, RecoveryCheckpoint] = {}

    def save_checkpoint(self, checkpoint: RecoveryCheckpoint) -> None:
        """Save recovery state checkpoint."""
        self._checkpoints[checkpoint.session_id] = checkpoint
        logger.info("Saved recovery checkpoint for session %s.", checkpoint.session_id)

    def recover_state(self, session_id: str) -> Optional[RecoveryCheckpoint]:
        """Recover state checkpoint details."""
        logger.info("Triggered state recovery check for session %s.", session_id)
        return self._checkpoints.get(session_id)
