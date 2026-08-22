"""R53 Validation events for EventBus publishing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class ValidationEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ValidationRunStarted(ValidationEvent):
    run_id: str
    checker_count: int


class ValidationRunCompleted(ValidationEvent):
    run_id: str
    passed: int
    failed: int
    warned: int
    certified: bool


class CheckFailed(ValidationEvent):
    check_name: str
    message: str
