"""R52 Runtime Logger — records runtime engine loop ticks, exceptions, and status changes.
"""

from __future__ import annotations

import logging
from research_platform.logging.rotation import create_rotating_file_handler
from research_platform.logging.formatter import StructuredJsonFormatter

_runtime_logger = logging.getLogger("toji.runtime")
if not _runtime_logger.handlers:
    _h = create_rotating_file_handler("logs", "runtime.log", formatter=StructuredJsonFormatter())
    _runtime_logger.addHandler(_h)
    _runtime_logger.setLevel(logging.DEBUG)
    _runtime_logger.propagate = False


class RuntimeLogger:
    """Emits structured runtime loop event records to runtime.log."""

    def tick(self, loop_name: str, iteration: int, duration_ms: float) -> None:
        _runtime_logger.debug(
            "TICK | loop=%s | iter=%d | duration_ms=%.3f", loop_name, iteration, duration_ms,
            extra={"correlation_id": loop_name, "extra_data": {"iter": iteration, "duration_ms": duration_ms}}
        )

    def loop_error(self, loop_name: str, error: str) -> None:
        _runtime_logger.error(
            "LOOP_ERROR | loop=%s | error=%s", loop_name, error,
            extra={"correlation_id": loop_name, "extra_data": {"error": error}}
        )

    def status_change(self, loop_name: str, old_status: str, new_status: str) -> None:
        _runtime_logger.info(
            "STATUS | loop=%s | %s -> %s", loop_name, old_status, new_status,
            extra={"correlation_id": loop_name, "extra_data": {"old": old_status, "new": new_status}}
        )
