"""Structured Logging — JSON-ready, per-module loggers.

Public API:
    - ``IStructuredLogger`` — abstract interface
    - ``StructuredLogger`` — default implementation
    - ``JsonFormatter`` — JSON log formatter
    - ``get_logger`` — convenience factory
"""

from toji_platform.core.logging.interfaces import IStructuredLogger
from toji_platform.core.logging.logger import JsonFormatter, StructuredLogger, get_logger

__all__ = [
    "IStructuredLogger",
    "JsonFormatter",
    "StructuredLogger",
    "get_logger",
]
