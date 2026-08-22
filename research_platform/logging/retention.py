"""R52 Log retention policy — prunes old log files beyond the retention window.
"""

from __future__ import annotations

import os
import time
import logging

logger = logging.getLogger(__name__)


class RetentionPolicy:
    """Deletes log files older than a configured number of days."""

    def __init__(self, log_dir: str, max_age_days: int = 90) -> None:
        self.log_dir = log_dir
        self.max_age_days = max_age_days

    def prune(self) -> int:
        """Remove stale log files. Returns count of deleted files."""
        deleted = 0
        cutoff = time.time() - (self.max_age_days * 86400)
        if not os.path.isdir(self.log_dir):
            return 0
        for fname in os.listdir(self.log_dir):
            fpath = os.path.join(self.log_dir, fname)
            if os.path.isfile(fpath):
                try:
                    mtime = os.path.getmtime(fpath)
                    if mtime < cutoff:
                        os.remove(fpath)
                        deleted += 1
                        logger.info("Pruned old log file: %s", fpath)
                except Exception as e:
                    logger.warning("Could not prune %s: %s", fpath, e)
        return deleted
