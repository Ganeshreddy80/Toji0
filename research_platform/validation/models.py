"""R53 Continuous Validation Pydantic Models.
"""

from __future__ import annotations

import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    RUNNING = "RUNNING"


class ValidationDuration(str, Enum):
    QUICK = "QUICK"           # < 1 minute
    HOURLY = "HOURLY"         # 1 hour
    DAILY = "DAILY"           # 24 hours
    THREE_DAY = "THREE_DAY"   # 72 hours
    WEEKLY = "WEEKLY"         # 7 days
    MONTHLY = "MONTHLY"       # 30 days


class CheckResult(BaseModel):
    """Result of a single validation check."""
    check_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    check_name: str
    status: CheckStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class ValidationRun(BaseModel):
    """Aggregated validation run comprising multiple checks."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration: ValidationDuration = ValidationDuration.QUICK
    results: List[CheckResult] = Field(default_factory=list)
    overall_status: CheckStatus = CheckStatus.RUNNING
    certified: bool = False

    def summarize(self) -> Dict[str, int]:
        counts: Dict[str, int] = {s.value: 0 for s in CheckStatus}
        for r in self.results:
            counts[r.status.value] += 1
        return counts


class CertificationReport(BaseModel):
    """Platform certification report."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    duration: ValidationDuration
    passed: int
    failed: int
    warned: int
    certified: bool
    summary: str
    details: List[CheckResult] = Field(default_factory=list)
