"""Thread-safe AWS Infrastructure Manager Coordinator (Sprint 12A)."""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.aws_config import AWSConfig, AWSConfigManager
from infrastructure.aws_credentials import AWSCredentialManager, AWSCredentialsDescriptor
from infrastructure.aws_session import AWSSessionManager, SessionRecord
from infrastructure.cloudwatch_logger import CloudWatchLogEvent, CloudWatchLogger, LogLevel
from infrastructure.infrastructure_events import (
    CredentialsLoaded,
    InfrastructureInitialized,
    LogBatchFlushed,
    ObjectDownloaded,
    ObjectUploaded,
    ParameterRegistered,
    SecretRegistered,
    SessionCreated,
)
from infrastructure.parameter_store import ParameterDescriptor, ParameterStore
from infrastructure.s3_storage import S3ObjectMetadata, S3Storage
from infrastructure.secrets_manager import SecretDescriptor, SecretsManager
from toji_platform.core.event_bus.interfaces import IEventBus

logger = logging.getLogger(__name__)


class InfrastructureManager:
    """Thread-safe Infrastructure Manager coordinating configuration, credentials, sessions, secrets, parameters, S3, and CloudWatch."""

    def __init__(
        self,
        event_bus: Optional[IEventBus] = None,
        config: Optional[AWSConfig] = None,
        credential_mgr: Optional[AWSCredentialManager] = None,
        session_mgr: Optional[AWSSessionManager] = None,
        secrets_mgr: Optional[SecretsManager] = None,
        parameter_store: Optional[ParameterStore] = None,
        s3_storage: Optional[S3Storage] = None,
        cloudwatch_logger: Optional[CloudWatchLogger] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._event_bus = event_bus
        self._config = config or AWSConfigManager.load_config()
        self._credential_mgr = credential_mgr or AWSCredentialManager()
        self._session_mgr = session_mgr or AWSSessionManager(
            config=self._config,
            credential_manager=self._credential_mgr,
        )
        self._secrets_mgr = secrets_mgr or SecretsManager()
        self._parameter_store = parameter_store or ParameterStore()
        self._s3_storage = s3_storage or S3Storage()
        self._cw_logger = cloudwatch_logger or CloudWatchLogger()

        self._initialized = False

    def initialize(self) -> SessionRecord:
        """Initialize infrastructure components, setup session, and publish event."""
        with self._lock:
            creds_desc = self._credential_mgr.get_descriptor()

            if self._event_bus:
                self._event_bus.publish(
                    CredentialsLoaded(
                        provider_type=creds_desc.provider_type,
                        access_key_id_masked=creds_desc.access_key_id_masked,
                    )
                )

            session_rec = self._session_mgr.get_session()
            if self._event_bus:
                self._event_bus.publish(
                    SessionCreated(
                        session_id=session_rec.session_id,
                        region=session_rec.region,
                    )
                )

            self._initialized = True
            logger.info("Initialized InfrastructureManager in region '%s' (env='%s')", self._config.region, self._config.environment.value)

            if self._event_bus:
                self._event_bus.publish(
                    InfrastructureInitialized(
                        region=self._config.region,
                        environment=self._config.environment.value,
                    )
                )
            return session_rec

    def register_secret(self, secret_name: str, arn: Optional[str] = None, description: str = "") -> SecretDescriptor:
        """Register a secret descriptor and publish event."""
        with self._lock:
            desc = self._secrets_mgr.register_secret(secret_name, arn, description)
            if self._event_bus:
                self._event_bus.publish(
                    SecretRegistered(
                        secret_name=desc.secret_name,
                        arn=desc.arn,
                    )
                )
            return desc

    def register_parameter(self, name: str, value: Any, value_type: str = "String") -> ParameterDescriptor:
        """Register an SSM parameter and publish event."""
        with self._lock:
            desc = self._parameter_store.register_parameter(name, value, value_type)
            if self._event_bus:
                self._event_bus.publish(
                    ParameterRegistered(
                        parameter_name=desc.name,
                        version=desc.version,
                    )
                )
            return desc

    def upload_s3_object(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> S3ObjectMetadata:
        """Upload object to S3 storage abstraction and publish event."""
        with self._lock:
            meta = self._s3_storage.upload_object(bucket, key, data, content_type)
            if self._event_bus:
                self._event_bus.publish(
                    ObjectUploaded(
                        bucket=meta.bucket,
                        key=meta.key,
                        size_bytes=meta.size_bytes,
                        checksum=meta.checksum,
                    )
                )
            return meta

    def download_s3_object(self, bucket: str, key: str) -> Tuple[bytes, S3ObjectMetadata]:
        """Download object from S3 storage abstraction and publish event."""
        with self._lock:
            data, meta = self._s3_storage.download_object(bucket, key)
            if self._event_bus:
                self._event_bus.publish(
                    ObjectDownloaded(
                        bucket=meta.bucket,
                        key=meta.key,
                        size_bytes=meta.size_bytes,
                    )
                )
            return data, meta

    def log_cloudwatch(self, message: str, level: LogLevel = LogLevel.INFO, extra: Optional[Dict[str, Any]] = None) -> CloudWatchLogEvent:
        """Enqueue structured log event."""
        with self._lock:
            return self._cw_logger.log(message, level=level, extra=extra)

    def flush_cloudwatch_logs(self, batch_size: int = 100) -> List[CloudWatchLogEvent]:
        """Flush enqueued CloudWatch log events and publish event."""
        with self._lock:
            batch = self._cw_logger.flush_batch(batch_size)
            if self._event_bus and batch:
                self._event_bus.publish(
                    LogBatchFlushed(
                        log_group=batch[0].log_group,
                        log_stream=batch[0].log_stream,
                        event_count=len(batch),
                    )
                )
            return batch

    # Sub-component accessors
    @property
    def config(self) -> AWSConfig:
        return self._config

    @property
    def credential_manager(self) -> AWSCredentialManager:
        return self._credential_mgr

    @property
    def session_manager(self) -> AWSSessionManager:
        return self._session_mgr

    @property
    def secrets_manager(self) -> SecretsManager:
        return self._secrets_mgr

    @property
    def parameter_store(self) -> ParameterStore:
        return self._parameter_store

    @property
    def s3_storage(self) -> S3Storage:
        return self._s3_storage

    @property
    def cloudwatch_logger(self) -> CloudWatchLogger:
        return self._cw_logger

    def clear(self) -> None:
        """Clear state across all managed infrastructure sub-components."""
        with self._lock:
            self._session_mgr.reset_session()
            self._secrets_mgr.clear()
            self._parameter_store.clear()
            self._s3_storage.clear()
            self._cw_logger.clear()
            self._initialized = False
