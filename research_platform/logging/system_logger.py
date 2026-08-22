"""R52 System Logger — boot, shutdown, plugin registration, and platform lifecycle events.
"""

from __future__ import annotations

import logging
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_sys_logger = logging.getLogger("toji.system")
if not _sys_logger.handlers:
    _h = create_rotating_file_handler("logs", "system.log", formatter=StructuredJsonFormatter())
    _sys_logger.addHandler(_h)
    _sys_logger.setLevel(logging.DEBUG)
    _sys_logger.propagate = False


class SystemLogger:
    """Records platform boot and shutdown lifecycle events to system.log."""

    def boot_started(self) -> None:
        _sys_logger.info("BOOT_STARTED", extra={"correlation_id": "BOOT", "extra_data": {}})

    def boot_complete(self, plugin_count: int) -> None:
        _sys_logger.info(
            "BOOT_COMPLETE | plugins=%d", plugin_count,
            extra={"correlation_id": "BOOT", "extra_data": {"plugin_count": plugin_count}}
        )

    def shutdown_started(self) -> None:
        _sys_logger.info("SHUTDOWN_STARTED", extra={"correlation_id": "SHUTDOWN", "extra_data": {}})

    def shutdown_complete(self) -> None:
        _sys_logger.info("SHUTDOWN_COMPLETE", extra={"correlation_id": "SHUTDOWN", "extra_data": {}})

    def plugin_registered(self, name: str) -> None:
        _sys_logger.info(
            "PLUGIN_REGISTERED | name=%s", name,
            extra={"correlation_id": "BOOT", "extra_data": {"plugin": name}}
        )

    def error(self, msg: str, error: str = "") -> None:
        _sys_logger.error(
            "SYSTEM_ERROR | %s | error=%s", msg, error,
            extra={"correlation_id": "SYSTEM", "extra_data": {"error": error}}
        )
