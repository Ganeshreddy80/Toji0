"""R53 Database checker — verifies PostgreSQL connectivity."""

from __future__ import annotations

import time
import logging
from research_platform.validation.interfaces import IChecker
from research_platform.validation.models import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


class DatabaseChecker(IChecker):
    @property
    def name(self) -> str:
        return "DatabaseConnectivityChecker"

    def run(self) -> CheckResult:
        start = time.perf_counter()
        try:
            from research_platform.platform.service_registry import ServiceRegistry
            registry = ServiceRegistry()
            db = registry.get_service("Database")
            duration_ms = (time.perf_counter() - start) * 1000
            if db is None:
                return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                                   duration_ms=duration_ms,
                                   message="Database service not registered in DI container")
            # Try a lightweight connectivity check
            try:
                with db.connect() as conn:
                    conn.execute(__import__("sqlalchemy").text("SELECT 1"))
                return CheckResult(check_name=self.name, status=CheckStatus.PASS,
                                   duration_ms=duration_ms,
                                   message="PostgreSQL connectivity verified")
            except Exception as conn_err:
                return CheckResult(check_name=self.name, status=CheckStatus.FAIL,
                                   duration_ms=duration_ms,
                                   message=f"DB connectivity failed: {conn_err}")
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return CheckResult(check_name=self.name, status=CheckStatus.WARN,
                               duration_ms=duration_ms, message=str(e))
