from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class ExecutionAuditRecord(BaseModel):
    """Immutable record tracking execution state changes and actor decisions."""

    audit_id: str = Field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:8]}", description="Unique audit record identifier.")
    execution_id: str = Field(..., description="Target execution flow UUID.")
    correlation_id: str = Field(..., description="Audit trace correlation identifier.")
    actor: str = Field(..., description="Entity triggering the change (e.g. validator, engine, broker).")
    action: str = Field(..., description="Operation performed (e.g. SUBMIT, STATE_TRANSITION, REJECTION).")
    before: Dict[str, Any] = Field(default_factory=dict, description="State before operation.")
    after: Dict[str, Any] = Field(default_factory=dict, description="State after operation.")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Audit timestamp.")
    reason: Optional[str] = Field(default=None, description="Context explanation.")

    model_config = ConfigDict(frozen=True)
