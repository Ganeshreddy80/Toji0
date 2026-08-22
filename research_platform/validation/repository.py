"""R53 Validation repository — persists ValidationRuns and CertificationReports."""

from __future__ import annotations

import threading
import logging
from collections import deque
from typing import Deque, Optional, List
from research_platform.validation.models import ValidationRun, CertificationReport

logger = logging.getLogger(__name__)
MAX_HISTORY = 100


class ValidationRepository:
    """Thread-safe in-memory store for recent validation runs and certification reports."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Deque[ValidationRun] = deque(maxlen=MAX_HISTORY)
        self._certs: Deque[CertificationReport] = deque(maxlen=MAX_HISTORY)

    def save_run(self, run: ValidationRun) -> None:
        with self._lock:
            self._runs.append(run)
        self._try_persist_run(run)

    def save_certification(self, cert: CertificationReport) -> None:
        with self._lock:
            self._certs.append(cert)
        self._try_persist_cert(cert)

    def get_latest_run(self) -> Optional[ValidationRun]:
        with self._lock:
            return self._runs[-1] if self._runs else None

    def get_latest_certification(self) -> Optional[CertificationReport]:
        with self._lock:
            return self._certs[-1] if self._certs else None

    def get_all_certifications(self) -> List[CertificationReport]:
        with self._lock:
            return list(self._certs)

    def _try_persist_run(self, run: ValidationRun) -> None:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
            from research_platform.configuration.models import ConfigurationEntry
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            registry = ServiceRegistry()
            db = registry.get_service("Database")
            if db:
                sm = DatabaseSessionManager(db)
                repo = PostgresConfigurationRepository(sm)
                repo.save_config(ConfigurationEntry(key=f"validation_run:{run.run_id}", value=run.model_dump()))
        except Exception as e:
            logger.debug("Validation run persistence skipped: %s", e)

    def _try_persist_cert(self, cert: CertificationReport) -> None:
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            from research_platform.persistence.repositories.configuration_repository import PostgresConfigurationRepository
            from research_platform.configuration.models import ConfigurationEntry
            from research_platform.persistence.postgres.session import DatabaseSessionManager
            registry = ServiceRegistry()
            db = registry.get_service("Database")
            if db:
                sm = DatabaseSessionManager(db)
                repo = PostgresConfigurationRepository(sm)
                repo.save_config(ConfigurationEntry(key=f"certification:{cert.report_id}", value=cert.model_dump()))
        except Exception as e:
            logger.debug("Certification persistence skipped: %s", e)
