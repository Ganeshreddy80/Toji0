"""Thread-safe AWS Session Manager with Lazy Initialization and Client Injection (Sprint 12A)."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field

from infrastructure.aws_config import AWSConfig
from infrastructure.aws_credentials import AWSCredentialManager, AWSCredentialsDescriptor

logger = logging.getLogger(__name__)


class SessionRecord(BaseModel):
    """Immutable record of an active AWS session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    region: str = Field(..., description="AWS region for the session.")
    environment: str = Field(..., description="Target environment.")
    credentials_descriptor: AWSCredentialsDescriptor = Field(..., description="Masked credentials.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)


class MockAWSClient:
    """Generic mock client used during testing/offline operation to prevent live network calls."""

    def __init__(self, service_name: str, region: str) -> None:
        self.service_name = service_name
        self.region = region
        self._calls: list = []

    def call_action(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        self._calls.append((action, kwargs))
        return {"status": "success", "service": self.service_name, "action": action}


class AWSSessionManager:
    """Thread-safe AWS Session Manager supporting lazy initialization and client injection."""

    def __init__(
        self,
        config: Optional[AWSConfig] = None,
        credential_manager: Optional[AWSCredentialManager] = None,
        client_factory: Optional[Callable[[str, AWSConfig], Any]] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._config = config or AWSConfig()
        self._credential_manager = credential_manager or AWSCredentialManager()
        self._client_factory = client_factory or self._default_client_factory
        self._session_record: Optional[SessionRecord] = None
        self._clients: Dict[str, Any] = {}

    def get_session(self) -> SessionRecord:
        """Get or lazily initialize the active AWS session."""
        with self._lock:
            if self._session_record is None:
                creds = self._credential_manager.get_descriptor()
                self._session_record = SessionRecord(
                    region=self._config.region,
                    environment=self._config.environment.value,
                    credentials_descriptor=creds,
                )
                logger.info("Initialized AWSSession '%s' in region '%s'", self._session_record.session_id, self._config.region)
            return self._session_record

    def get_client(self, service_name: str) -> Any:
        """Reuse or construct an AWS client for the requested service_name."""
        with self._lock:
            if service_name not in self._clients:
                self.get_session()  # Ensure session is active
                client = self._client_factory(service_name, self._config)
                self._clients[service_name] = client
                logger.info("Constructed client for service '%s'", service_name)
            return self._clients[service_name]

    def reset_session(self) -> None:
        """Reset active session and cached clients."""
        with self._lock:
            self._session_record = None
            self._clients.clear()

    def _default_client_factory(self, service_name: str, config: AWSConfig) -> Any:
        """Default mock client factory ensuring zero network calls during tests."""
        return MockAWSClient(service_name=service_name, region=config.region)
