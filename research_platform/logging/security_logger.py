"""R52 Security Logger — records access violations, suspicious events, and auth failures.
"""

from __future__ import annotations

import logging
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_sec_logger = logging.getLogger("toji.security")
if not _sec_logger.handlers:
    _h = create_rotating_file_handler("logs", "security.log", formatter=StructuredJsonFormatter())
    _sec_logger.addHandler(_h)
    _sec_logger.setLevel(logging.WARNING)
    _sec_logger.propagate = False


class SecurityLogger:
    """Emits security alert events to security.log."""

    def access_denied(self, resource: str, actor: str, reason: str) -> None:
        _sec_logger.warning(
            "ACCESS_DENIED | resource=%s | actor=%s | reason=%s", resource, actor, reason,
            extra={"correlation_id": actor, "extra_data": {"resource": resource, "reason": reason}}
        )

    def suspicious_activity(self, description: str, details: str = "") -> None:
        _sec_logger.error(
            "SUSPICIOUS | %s | details=%s", description, details,
            extra={"correlation_id": "SECURITY", "extra_data": {"details": details}}
        )

    def auth_failure(self, actor: str, reason: str) -> None:
        _sec_logger.warning(
            "AUTH_FAILURE | actor=%s | reason=%s", actor, reason,
            extra={"correlation_id": actor, "extra_data": {"reason": reason}}
        )
