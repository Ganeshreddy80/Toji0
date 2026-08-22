"""R52 Audit Logger — records configuration changes, operator actions, and system events.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from research_platform.logging.interfaces import IAuditLogger
from research_platform.logging.models import AuditRecord
from research_platform.logging.rotation import create_timed_rotating_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_audit_logger = logging.getLogger("toji.audit")
if not _audit_logger.handlers:
    _h = create_timed_rotating_handler("logs", "audit.log", formatter=StructuredJsonFormatter())
    _audit_logger.addHandler(_h)
    _audit_logger.setLevel(logging.DEBUG)
    _audit_logger.propagate = False


class AuditLogger(IAuditLogger):
    """Persists structured audit records to audit.log."""

    def log_audit(self, record: AuditRecord) -> None:
        extra = {
            "correlation_id": record.action,
            "extra_data": {
                "actor": record.actor,
                "success": record.success,
                "change_summary": record.change_summary,
                "details": record.details,
            }
        }
        msg = f"AUDIT | {record.action} | actor={record.actor} | success={record.success} | {record.change_summary}"
        _audit_logger.info(msg, extra=extra)

    def record(self, action: str, actor: str = "SYSTEM", success: bool = True, summary: str = "", details: Optional[Dict[str, Any]] = None) -> None:
        rec = AuditRecord(action=action, actor=actor, success=success, change_summary=summary, details=details or {})
        self.log_audit(rec)
