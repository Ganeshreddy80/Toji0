"""Exceptions for the Dashboard Platform subsystem."""

from __future__ import annotations


class DashboardError(Exception):
    """Base exception for all dashboard-related issues."""


class StateStoreError(DashboardError):
    """Exception raised by the DashboardStateStore."""


class RepositoryError(DashboardError):
    """Exception raised by the DashboardRepository."""


class OrchestratorError(DashboardError):
    """Exception raised by the DashboardOrchestrator."""
