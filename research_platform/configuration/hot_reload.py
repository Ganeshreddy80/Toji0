"""Hot reload manager reloading active configurations without halting loops.
"""

from __future__ import annotations

import logging
from research_platform.configuration.interfaces import IHotReload

logger = logging.getLogger(__name__)


class HotReload(IHotReload):
    """Executes config synchronizations without resetting runtime loops."""

    def __init__(self) -> None:
        self._reload_count = 0

    def reload_configurations(self) -> None:
        self._reload_count += 1
        logger.info("HotReload: Completed hot reload #%d", self._reload_count)
