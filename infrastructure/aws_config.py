"""Immutable AWS Configuration Model and Manager (Sprint 12A)."""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)


class AWSEnvironment(str, Enum):
    """Allowed deployment environment names."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class AWSConfig(BaseModel):
    """Immutable AWS Infrastructure Configuration Model."""

    region: str = Field(default="us-east-1", description="Target AWS region.")
    environment: AWSEnvironment = Field(default=AWSEnvironment.DEV, description="Environment selector.")
    profile_name: Optional[str] = Field(default=None, description="AWS CLI profile name.")
    endpoint_url: Optional[str] = Field(default=None, description="Custom endpoint URL for local/testing mocks.")
    timeout_seconds: float = Field(default=30.0, gt=0.0, description="Connection/read timeout in seconds.")
    retry_attempts: int = Field(default=3, ge=0, description="Maximum client retries.")
    max_connections: int = Field(default=10, gt=0, description="Max HTTP connections in pool.")
    is_advisory_only: bool = Field(default=True, description="Advisory flag.")

    model_config = ConfigDict(frozen=True)

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("AWS region must not be empty.")
        return v.strip().lower()


class AWSConfigManager:
    """Helper to load and validate AWSConfig from environment variables or dictionary inputs."""

    @staticmethod
    def load_config(
        overrides: Optional[Dict[str, Any]] = None,
    ) -> AWSConfig:
        """Load configuration combining environment variables and explicit overrides."""
        env_vars: Dict[str, Any] = {}

        if "AWS_REGION" in os.environ:
            env_vars["region"] = os.environ["AWS_REGION"]
        elif "AWS_DEFAULT_REGION" in os.environ:
            env_vars["region"] = os.environ["AWS_DEFAULT_REGION"]

        if "TOJI_ENV" in os.environ:
            env_vars["environment"] = os.environ["TOJI_ENV"].lower()

        if "AWS_PROFILE" in os.environ:
            env_vars["profile_name"] = os.environ["AWS_PROFILE"]

        if "AWS_ENDPOINT_URL" in os.environ:
            env_vars["endpoint_url"] = os.environ["AWS_ENDPOINT_URL"]

        merged = {**env_vars, **(overrides or {})}
        config = AWSConfig(**merged)
        logger.info("Loaded AWSConfig: region='%s', env='%s'", config.region, config.environment.value)
        return config
