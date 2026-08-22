"""Thread-safe Secrets Manager Abstraction with Bounded Cache (Sprint 12A)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class SecretDescriptor(BaseModel):
    """Immutable metadata descriptor for a managed secret (never stores secret values)."""

    secret_name: str = Field(..., description="Target secret name.")
    arn: str = Field(..., description="AWS Secrets Manager ARN.")
    version_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class SecretsManager:
    """Thread-safe Secrets Manager managing metadata descriptors with bounded capacity (up to 1,000 secrets)."""

    def __init__(self, max_secrets: int = 1000) -> None:
        self._lock = threading.RLock()
        self._max_secrets = max_secrets
        # secret_name -> SecretDescriptor
        self._secrets: Dict[str, SecretDescriptor] = {}

    def register_secret(
        self,
        secret_name: str,
        arn: Optional[str] = None,
        description: str = "",
    ) -> SecretDescriptor:
        """Register secret metadata descriptor."""
        with self._lock:
            if len(self._secrets) >= self._max_secrets:
                oldest_name = next(iter(self._secrets))
                del self._secrets[oldest_name]

            secret_arn = arn or f"arn:aws:secretsmanager:us-east-1:123456789012:secret:{secret_name}"
            descriptor = SecretDescriptor(
                secret_name=secret_name,
                arn=secret_arn,
                description=description,
            )
            self._secrets[secret_name] = descriptor
            logger.info("Registered secret descriptor for '%s' (arn='%s')", secret_name, secret_arn)
            return descriptor

    def get_secret_reference(self, secret_name: str) -> Optional[SecretDescriptor]:
        """Retrieve secret metadata descriptor by name."""
        with self._lock:
            return self._secrets.get(secret_name)

    def list_secrets(self) -> List[SecretDescriptor]:
        """List all registered secret descriptors."""
        with self._lock:
            return list(self._secrets.values())

    def count(self) -> int:
        """Return total count of cached secrets."""
        with self._lock:
            return len(self._secrets)

    def clear(self) -> None:
        """Clear all cached secret descriptors."""
        with self._lock:
            self._secrets.clear()
