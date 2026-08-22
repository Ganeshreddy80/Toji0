"""R52 Logging Framework Pydantic Models.
"""

from __future__ import annotations

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class LogSeverity(str, Enum):
    """Custom log severities for quantitative logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    AUDIT = "AUDIT"
    TRADE = "TRADE"
    PERFORMANCE = "PERFORMANCE"
    SECURITY = "SECURITY"


class LogRecord(BaseModel):
    """General structural log representation."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    severity: LogSeverity
    component: str
    message: str
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data: Dict[str, Any] = Field(default_factory=dict)


class AuditRecord(BaseModel):
    """User command intervention and configuration hot-reload logs."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str
    actor: str = "SYSTEM"
    success: bool = True
    change_summary: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class TradeLogRecord(BaseModel):
    """Order placement and execution updates logging."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    order_id: str
    side: str
    symbol: str
    quantity: float
    price: float
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)


class PerfRecord(BaseModel):
    """Latency metrics and hardware statistics logs."""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operation: str
    duration_ms: float
    cpu_pct: float = 0.0
    memory_mb: float = 0.0
