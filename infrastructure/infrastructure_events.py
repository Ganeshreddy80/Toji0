"""Immutable AWS Infrastructure Event Models for the TOJI Platform (Sprint 12A)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class InfrastructureInitialized(BaseModel):
    """Event published when the AWS infrastructure subsystem is initialized."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="InfrastructureInitialized")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    region: str
    environment: str

    model_config = ConfigDict(frozen=True)


class CredentialsLoaded(BaseModel):
    """Event published when AWS credentials are loaded or refreshed."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="CredentialsLoaded")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider_type: str
    access_key_id_masked: str

    model_config = ConfigDict(frozen=True)


class SessionCreated(BaseModel):
    """Event published when an AWS session is established."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="SessionCreated")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str
    region: str

    model_config = ConfigDict(frozen=True)


class SecretRegistered(BaseModel):
    """Event published when secret metadata is registered."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="SecretRegistered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    secret_name: str
    arn: str

    model_config = ConfigDict(frozen=True)


class ParameterRegistered(BaseModel):
    """Event published when a parameter is registered in Parameter Store."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ParameterRegistered")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parameter_name: str
    version: int

    model_config = ConfigDict(frozen=True)


class ObjectUploaded(BaseModel):
    """Event published when an object is uploaded to S3 storage abstraction."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ObjectUploaded")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    bucket: str
    key: str
    size_bytes: int
    checksum: str

    model_config = ConfigDict(frozen=True)


class ObjectDownloaded(BaseModel):
    """Event published when an object is downloaded from S3 storage abstraction."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="ObjectDownloaded")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    bucket: str
    key: str
    size_bytes: int

    model_config = ConfigDict(frozen=True)


class LogBatchFlushed(BaseModel):
    """Event published when a batch of CloudWatch log records is flushed."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = Field(default="LogBatchFlushed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    log_group: str
    log_stream: str
    event_count: int

    model_config = ConfigDict(frozen=True)
