"""Immutable Pydantic models for the Execution Management System (EMS).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ExchangeBalance(BaseModel):
    """Account capital balance details on exchange."""

    asset: str
    free: float
    locked: float
    total: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExchangePosition(BaseModel):
    """Active asset position details on exchange."""

    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    margin_requirement: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExecutionReport(BaseModel):
    """EMS status report back to the OMS."""

    report_id: str
    order_id: str
    symbol: str
    status: str  # SUBMITTED, FILLED, REJECTED, CANCELLED
    filled_quantity: float
    avg_price: float
    commission: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ExecutionAudit(BaseModel):
    """Audit trace of connection and request parameters."""

    audit_id: str
    activity_type: str  # REST_REQUEST, WS_RECONNECT, RECONCILIATION
    details: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class HealthMetric(BaseModel):
    """Connectivity metrics logs."""

    metric_id: str
    latency_ms: float
    uptime_pct: float
    success_ratio: float
    reconnect_count: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)


class ReconciliationLog(BaseModel):
    """State audit tracking matches between local and exchange registers."""

    log_id: str
    discrepancies: List[str] = Field(default_factory=list)
    reconciled: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(frozen=True)
