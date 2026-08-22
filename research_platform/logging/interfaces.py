"""R52 Logging Framework Interfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from research_platform.logging.models import AuditRecord, TradeLogRecord, LogSeverity


class ILogger(ABC):
    """General abstract contract for structured subsystem logs."""

    @abstractmethod
    def log(self, severity: LogSeverity, component: str, message: str, correlation_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> None:
        """Structured log emission."""
        pass


class IAuditLogger(ABC):
    """Abstract contract for audit logs."""

    @abstractmethod
    def log_audit(self, record: AuditRecord) -> None:
        """Structured audit log emission."""
        pass


class ITradeLogger(ABC):
    """Abstract contract for trade execution logs."""

    @abstractmethod
    def log_trade(self, record: TradeLogRecord) -> None:
        """Structured trade logs emission."""
        pass
