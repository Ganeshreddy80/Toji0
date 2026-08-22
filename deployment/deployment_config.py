"""Immutable Deployment Configuration Model for Container Deployment (Sprint 12B)."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class DeploymentEnvironment(str, Enum):
    """Target deployment environment names."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class DeploymentStrategy(str, Enum):
    """Allowed container deployment strategy types."""

    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"


class DeploymentConfig(BaseModel):
    """Immutable Deployment Configuration Model."""

    environment: DeploymentEnvironment = Field(default=DeploymentEnvironment.DEV, description="Target environment.")
    cpu_allocation: float = Field(default=1.0, gt=0.0, description="Allocated CPU cores.")
    memory_allocation_mb: int = Field(default=512, gt=0, description="Allocated memory in MB.")
    replica_count: int = Field(default=1, ge=1, description="Number of replica instances.")
    deployment_strategy: DeploymentStrategy = Field(
        default=DeploymentStrategy.ROLLING, description="Deployment rollout strategy."
    )
    env_variables: Dict[str, str] = Field(default_factory=dict, description="Environment variables dictionary.")
    max_cpu_limit: float = Field(default=4.0, gt=0.0, description="Maximum CPU threshold limit.")
    max_memory_limit_mb: int = Field(default=4096, gt=0, description="Maximum Memory threshold limit in MB.")
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)

    @field_validator("cpu_allocation")
    @classmethod
    def validate_cpu(cls, v: float) -> float:
        if v <= 0.0 or v > 64.0:
            raise ValueError(f"CPU allocation {v} out of valid range (0.0, 64.0].")
        return v

    @field_validator("memory_allocation_mb")
    @classmethod
    def validate_memory(cls, v: int) -> int:
        if v < 64 or v > 262144:
            raise ValueError(f"Memory allocation {v} MB out of valid range [64 MB, 256 GB].")
        return v
