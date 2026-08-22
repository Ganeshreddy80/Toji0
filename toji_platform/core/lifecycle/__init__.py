"""Lifecycle Manager — ordered startup, shutdown, and health checks.

Public API:
    - ``ILifecycle`` — interface for managed components
    - ``IHealthCheck`` — health probe interface
    - ``LifecycleManager`` — orchestrates startup/shutdown
"""

from toji_platform.core.lifecycle.interfaces import IHealthCheck, ILifecycle
from toji_platform.core.lifecycle.manager import LifecycleManager
from toji_platform.core.lifecycle.heartbeat import HeartbeatScheduler

__all__ = ["IHealthCheck", "ILifecycle", "LifecycleManager", "HeartbeatScheduler"]
