"""Immutable Deployment Descriptor Model (Sprint 12B)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from deployment.deployment_config import DeploymentConfig

logger = logging.getLogger(__name__)


class DeploymentStatus(str, Enum):
    """Lifecycle states of a deployment process."""

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


class DeploymentDescriptor(BaseModel):
    """Immutable Deployment Descriptor Record."""

    deployment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = Field(..., description="Target service name.")
    version: str = Field(default="1.0.0", description="Target service version.")
    environment: str = Field(default="dev", description="Target environment.")
    status: DeploymentStatus = Field(default=DeploymentStatus.CREATED, description="Lifecycle status.")
    config: DeploymentConfig = Field(default_factory=DeploymentConfig, description="Deployment configuration.")
    plan_summary: Dict[str, Any] = Field(default_factory=dict, description="Summary of deployment plan.")
    error_message: Optional[str] = Field(default=None, description="Error message if validation or planning failed.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    validated_at: Optional[datetime] = Field(default=None)
    approved_at: Optional[datetime] = Field(default=None)
    archived_at: Optional[datetime] = Field(default=None)
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)
