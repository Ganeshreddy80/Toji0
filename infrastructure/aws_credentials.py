"""Thread-safe AWS Credential Manager and Masked Credential Descriptor (Sprint 12A)."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class AWSCredentialsDescriptor(BaseModel):
    """Immutable descriptor of AWS credentials with sensitive values masked."""

    access_key_id: str = Field(..., description="Access Key ID.")
    provider_type: str = Field(default="env_or_profile", description="Source credential provider type.")
    access_key_id_masked: str = Field(..., description="Masked Access Key ID for display/logging.")
    has_secret_key: bool = Field(default=True, description="Flag indicating presence of secret key.")
    has_session_token: bool = Field(default=False, description="Flag indicating presence of session token.")
    expiration: Optional[datetime] = Field(default=None, description="Expiration timestamp if temporary.")
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class AWSCredentialManager:
    """Thread-safe Manager for loading, masking, and refreshing AWS credentials."""

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        session_token: Optional[str] = None,
        provider_type: str = "static",
    ) -> None:
        self._lock = threading.RLock()
        self._provider_type = provider_type
        self._access_key_id = access_key_id if access_key_id is not None else "MOCK_AKIA_DEFAULT_KEY"
        self._secret_access_key = secret_access_key if secret_access_key is not None else "MOCK_SECRET_ACCESS_KEY_SAFE"
        self._session_token = session_token
        self._expiration: Optional[datetime] = None

    def get_descriptor(self) -> AWSCredentialsDescriptor:
        """Get an immutable descriptor with all secrets safely masked."""
        with self._lock:
            masked_key = self._mask_string(self._access_key_id)
            return AWSCredentialsDescriptor(
                access_key_id=self._access_key_id,
                provider_type=self._provider_type,
                access_key_id_masked=masked_key,
                has_secret_key=bool(self._secret_access_key),
                has_session_token=bool(self._session_token),
                expiration=self._expiration,
            )

    def validate_credentials(self) -> bool:
        """Validate credential fields without making external network calls."""
        with self._lock:
            if not self._access_key_id or not self._secret_access_key:
                logger.warning("AWS credential validation failed: missing key or secret")
                return False
            return True

    def refresh_session(self, new_token: Optional[str] = None, new_expiration: Optional[datetime] = None) -> AWSCredentialsDescriptor:
        """Refresh temporary session token."""
        with self._lock:
            self._session_token = new_token
            self._expiration = new_expiration or datetime.now(timezone.utc)
            logger.info("Refreshed AWS session credentials (provider='%s')", self._provider_type)
            return self.get_descriptor()

    @staticmethod
    def _mask_string(val: str) -> str:
        if not val or len(val) <= 4:
            return "****"
        return f"{val[:4]}****{val[-2:]}"
