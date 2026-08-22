"""R52 Log rotation configuration.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from typing import Optional


def create_rotating_file_handler(
    log_dir: str,
    filename: str,
    max_bytes: int = 50 * 1024 * 1024,   # 50 MB
    backup_count: int = 10,
    formatter: Optional[logging.Formatter] = None
) -> logging.handlers.RotatingFileHandler:
    """Create a RotatingFileHandler writing to log_dir/filename."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, filename)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    if formatter:
        handler.setFormatter(formatter)
    return handler


def create_timed_rotating_handler(
    log_dir: str,
    filename: str,
    when: str = "midnight",
    backup_count: int = 30,
    formatter: Optional[logging.Formatter] = None
) -> logging.handlers.TimedRotatingFileHandler:
    """Create a TimedRotatingFileHandler rotating at midnight for 30 days retention."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, filename)
    handler = logging.handlers.TimedRotatingFileHandler(
        path, when=when, backupCount=backup_count, encoding="utf-8"
    )
    if formatter:
        handler.setFormatter(formatter)
    return handler
