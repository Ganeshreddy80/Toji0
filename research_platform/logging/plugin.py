"""R52 Logging & Audit Framework Plugin — platform DI integration."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class LoggingPlugin:
    """Registers R52 specialized loggers and repository in the DI container."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def initialize(self) -> None:
        logger.info("Initializing Logging & Audit Framework (R52)...")
        try:
            from research_platform.logging.audit_logger import AuditLogger
            from research_platform.logging.trade_logger import TradeLogger
            from research_platform.logging.performance_logger import PerformanceLogger
            from research_platform.logging.system_logger import SystemLogger
            from research_platform.logging.database_logger import DatabaseLogger
            from research_platform.logging.runtime_logger import RuntimeLogger
            from research_platform.logging.error_logger import ErrorLogger
            from research_platform.logging.security_logger import SecurityLogger
            from research_platform.logging.repository import LogRepository

            audit = AuditLogger()
            trade = TradeLogger()
            perf = PerformanceLogger()
            system = SystemLogger()
            db_log = DatabaseLogger()
            runtime_log = RuntimeLogger()
            err = ErrorLogger()
            sec = SecurityLogger()
            repo = LogRepository()

            self.container.register("AuditLogger", instance=audit)
            self.container.register("TradeLogger", instance=trade)
            self.container.register("PerformanceLogger", instance=perf)
            self.container.register("SystemLogger", instance=system)
            self.container.register("DatabaseLogger", instance=db_log)
            self.container.register("RuntimeLogger", instance=runtime_log)
            self.container.register("ErrorLogger", instance=err)
            self.container.register("SecurityLogger", instance=sec)
            self.container.register("LogRepository", instance=repo)
            self.container.register(AuditLogger, instance=audit)
            self.container.register(TradeLogger, instance=trade)
            self.container.register(LogRepository, instance=repo)

            from research_platform.platform.service_registry import ServiceRegistry
            ServiceRegistry().register_service("AuditLogger", audit)

            system.boot_started()
            logger.info("R52 LoggingPlugin initialized with 8 specialized loggers.")
        except Exception as e:
            logger.error("R52 LoggingPlugin initialization failed: %s", e)

    def shutdown(self) -> None:
        try:
            system_logger = self.container.resolve("SystemLogger")
            if system_logger:
                system_logger.shutdown_started()
                system_logger.shutdown_complete()
        except Exception:
            pass
        logger.info("R52 LoggingPlugin shutdown complete.")

    def health_check(self) -> str:
        return "HEALTHY"
