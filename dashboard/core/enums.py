"""Enums for the Dashboard Platform."""

from enum import Enum


class HealthStatus(str, Enum):
    """Subsystem operational status values."""

    HEALTHY = "Healthy"
    INITIALIZING = "Initializing"
    WARNING = "Warning"
    OFFLINE = "Offline"
    ERROR = "Error"
