"""R52 Central structured logger factory.
"""

from __future__ import annotations

import logging
import sys
import uuid
from typing import Any, Dict, Optional

from research_platform.logging.formatter import StructuredJsonFormatter
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.interfaces import ILogger
from research_platform.logging.models import LogSeverity, LogRecord


LOG_DIR = "logs"


def _build_root_logger(level: int = logging.DEBUG) -> None:
    """Configure the root logging setup with JSON file + console handlers."""
    root = logging.getLogger()
    if root.handlers:
        return  # Already configured

    root.setLevel(level)
    json_fmt = StructuredJsonFormatter()
    console_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_fmt)
    root.addHandler(ch)

    # JSON rotating file handler
    fh = create_rotating_file_handler(LOG_DIR, "toji.log", formatter=json_fmt)
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)


class TOJILogger(ILogger):
    """Structured subsystem logger wrapping Python logging with correlation IDs."""

    def __init__(self, component: str) -> None:
        self.component = component
        _build_root_logger()
        self._logger = logging.getLogger(f"toji.{component}")

    def log(
        self,
        severity: LogSeverity,
        component: str,
        message: str,
        correlation_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        extra = {
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "extra_data": data or {},
        }
        level_map = {
            LogSeverity.DEBUG: logging.DEBUG,
            LogSeverity.INFO: logging.INFO,
            LogSeverity.WARNING: logging.WARNING,
            LogSeverity.ERROR: logging.ERROR,
            LogSeverity.CRITICAL: logging.CRITICAL,
            LogSeverity.AUDIT: logging.INFO,
            LogSeverity.TRADE: logging.INFO,
            LogSeverity.PERFORMANCE: logging.DEBUG,
            LogSeverity.SECURITY: logging.WARNING,
        }
        self._logger.log(level_map.get(severity, logging.INFO), message, extra=extra)

    def debug(self, msg: str, **kw: Any) -> None:
        self.log(LogSeverity.DEBUG, self.component, msg, data=kw)

    def info(self, msg: str, **kw: Any) -> None:
        self.log(LogSeverity.INFO, self.component, msg, data=kw)

    def warning(self, msg: str, **kw: Any) -> None:
        self.log(LogSeverity.WARNING, self.component, msg, data=kw)

    def error(self, msg: str, **kw: Any) -> None:
        self.log(LogSeverity.ERROR, self.component, msg, data=kw)

    def critical(self, msg: str, **kw: Any) -> None:
        self.log(LogSeverity.CRITICAL, self.component, msg, data=kw)
