"""Immutable Container & Deployment Event Models for the TOJI Platform (Sprint 12B)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DeploymentCreated(BaseModel):
    """Event published when a deployment specification is created."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DeploymentCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployment_id: str
    service_name: str
    environment: str

    model_config = ConfigDict(frozen=True)


class DeploymentValidated(BaseModel):
    """Event published when a deployment is validated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DeploymentValidated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployment_id: str
    is_valid: bool
    error_count: int

    model_config = ConfigDict(frozen=True)


class DeploymentApproved(BaseModel):
    """Event published when a deployment is approved (advisory-only approval)."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DeploymentApproved")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployment_id: str
    approver: str

    model_config = ConfigDict(frozen=True)


class DeploymentCancelled(BaseModel):
    """Event published when a deployment is cancelled."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DeploymentCancelled")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployment_id: str
    reason: str

    model_config = ConfigDict(frozen=True)


class DeploymentArchived(BaseModel):
    """Event published when a completed or cancelled deployment is archived."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="DeploymentArchived")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deployment_id: str

    model_config = ConfigDict(frozen=True)


class ServiceRegistered(BaseModel):
    """Event published when a new service version is registered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ServiceRegistered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str
    version: str

    model_config = ConfigDict(frozen=True)


class HealthStatusUpdated(BaseModel):
    """Event published when a service's health status is updated."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="HealthStatusUpdated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str
    is_alive: bool
    is_ready: bool

    model_config = ConfigDict(frozen=True)


class RuntimeOperationPerformed(BaseModel):
    """Event published when an operation is performed on the container runtime abstraction."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="RuntimeOperationPerformed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    operation: str
    container_id: str
    status: str

    model_config = ConfigDict(frozen=True)
