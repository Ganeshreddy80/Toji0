"""R52 Structured JSON and console logging log formatters.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict


class StructuredJsonFormatter(logging.Formatter):
    """Custom log formatter generating structured JSON outputs for ELK / database indexing."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize python logging records into formatted JSON strings."""
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "severity": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "file": f"{record.pathname}:{record.lineno}",
            "thread": record.threadName
        }

        # Inject extra dictionary values
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = getattr(record, "correlation_id")
        if hasattr(record, "extra_data"):
            log_data["extra_data"] = getattr(record, "extra_data")

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)
