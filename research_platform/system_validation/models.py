"""Immutable Pydantic models for the End-to-End System Validation Framework.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ValidationCheck(BaseModel):
    """An individual validation check status card."""

    name: str
    description: str
    category: str
    passed: bool
    severity: ValidationSeverity = ValidationSeverity.ERROR
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(frozen=True)


class SubsystemHealth(BaseModel):
    """Aggregated checks stats for a specific platform component."""

    name: str
    checks: List[ValidationCheck] = Field(default_factory=list)
    failures: List[ValidationCheck] = Field(default_factory=list)
    duration_seconds: float = 0.0
    score: float = 100.0

    model_config = ConfigDict(frozen=True)


class PerformanceMetrics(BaseModel):
    """Validation process resources utilization snapshots."""

    validation_duration: float
    cpu_percent: float = 0.0
    memory_usage_mb: float = 0.0
    coverage_percent: float = 100.0

    model_config = ConfigDict(frozen=True)


class SystemCertificationCard(BaseModel):
    """The final cryptographic certification output card."""

    status: str  # PASSED or FAILED
    overall_score: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    critical_issues: List[str] = Field(default_factory=list)
    block_hash: str

    model_config = ConfigDict(frozen=True)
