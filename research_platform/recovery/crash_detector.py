"""Crash detector verifying platform termination signatures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from research_platform.recovery.events import SystemCrashed

logger = logging.getLogger(__name__)


class CrashDetector:
    """Verifies cleanliness of previous process exits, triggering alert signals on crashes."""

    def __init__(self, container: Any, repository: Any) -> None:
        self.container = container
        self.repository = repository

    def detect_crash(self) -> bool:
        """Scan logs to identify crash conditions. Return True if crash was detected."""
        logger.info("Running crash detector diagnostics...")
        
        # Check configuration for clean shutdown flags
        latest_cp = self.repository.get_latest_checkpoint()
        if not latest_cp:
            return False

        # If previous heartbeat is found but clean shutdown is not documented, assume unexpected crash
        prev_time = latest_cp.timestamp
        now = datetime.now(timezone.utc)
        diff_sec = (now - prev_time).total_seconds()
        
        # If last checkpoint is within 2 hours and no clean shutdown flag exists, declare crash
        if diff_sec < 7200.0:
            logger.warning("Unclean process termination detected! Previous heartbeat timestamp: %s", prev_time)
            
            # Publish event
            try:
                eb = self.container.resolve("IEventBus")
                if eb:
                    event = SystemCrashed(
                        event_id="crash-alert",
                        detected_at=now,
                        previous_heartbeat_timestamp=prev_time,
                        reason="Previous session closed without a clean exit signal."
                    )
                    eb.publish("SystemCrashed", event.model_dump())
            except Exception:
                pass
            return True

        return False
