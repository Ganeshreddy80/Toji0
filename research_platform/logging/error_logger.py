"""R52 Error Logger — captures exceptions with full stack traces and context.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Optional

from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_err_logger = logging.getLogger("toji.error")
if not _err_logger.handlers:
    _h = create_rotating_file_handler("logs", "errors.log", formatter=StructuredJsonFormatter())
    _err_logger.addHandler(_h)
    _err_logger.setLevel(logging.WARNING)
    _err_logger.propagate = False


class ErrorLogger:
    """Captures exceptions with context and stack traces to errors.log."""

    def capture(self, component: str, error: Exception, context: Optional[Any] = None) -> None:
        tb = traceback.format_exc()
        _err_logger.error(
            "EXCEPTION | component=%s | type=%s | msg=%s",
            component, type(error).__name__, str(error),
            extra={
                "correlation_id": component,
                "extra_data": {
                    "traceback": tb,
                    "context": str(context) if context else None,
                }
            },
            exc_info=True,
        )

    def warning(self, component: str, message: str) -> None:
        _err_logger.warning(
            "WARNING | component=%s | %s", component, message,
            extra={"correlation_id": component, "extra_data": {}}
        )
