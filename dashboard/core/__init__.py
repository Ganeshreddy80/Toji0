"""Core components for the Dashboard Platform."""

from dashboard.core.enums import HealthStatus
from dashboard.core.models import SubsystemHealth, DashboardSnapshot, HistoricalEvent
from dashboard.core.events import DashboardInitialized, DashboardShutdown
from dashboard.core.interfaces import IDashboardStateStore, IDashboardRepository
from dashboard.core.exceptions import (
    DashboardError,
    StateStoreError,
    RepositoryError,
    OrchestratorError,
)

__all__ = [
    "HealthStatus",
    "SubsystemHealth",
    "DashboardSnapshot",
    "HistoricalEvent",
    "DashboardInitialized",
    "DashboardShutdown",
    "IDashboardStateStore",
    "IDashboardRepository",
    "DashboardError",
    "StateStoreError",
    "RepositoryError",
    "OrchestratorError",
]
