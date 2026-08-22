"""Thread-safe In-Memory Maintenance Scheduler for Mission Control (Sprint 10C)."""

from __future__ import annotations

import collections
from datetime import datetime, timezone
from enum import Enum
import logging
import threading
import uuid
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class MaintenanceState(str, Enum):
    """Maintenance window execution state."""

    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class MaintenanceWindow(BaseModel):
    """Immutable Maintenance Window definition model."""

    window_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique maintenance window UUID.",
    )
    service_name: str = Field(..., description="Target service identifier.")
    start_time: datetime = Field(..., description="Scheduled window start timestamp.")
    end_time: datetime = Field(..., description="Scheduled window end timestamp.")
    description: str = Field(..., description="Maintenance justification.")
    state: MaintenanceState = Field(default=MaintenanceState.SCHEDULED, description="Current execution state.")
    operator: str = Field(default="SYSTEM", description="Operator creating the window.")

    model_config = ConfigDict(frozen=True)


class MaintenanceScheduler:
    """Thread-safe In-Memory Maintenance Scheduler managing maintenance windows and active windows."""

    def __init__(self, max_history: int = 500) -> None:
        self._lock = threading.RLock()
        self._windows: Dict[str, MaintenanceWindow] = {}
        self._active_services: Dict[str, str] = {}  # service_name -> window_id
        self._history: collections.deque[MaintenanceWindow] = collections.deque(maxlen=max_history)

    def schedule_maintenance(
        self,
        service_name: str,
        start_time: datetime,
        end_time: datetime,
        description: str,
        operator: str = "OPERATOR",
    ) -> MaintenanceWindow:
        """Schedule a new maintenance window."""
        with self._lock:
            window = MaintenanceWindow(
                service_name=service_name,
                start_time=start_time,
                end_time=end_time,
                description=description,
                state=MaintenanceState.SCHEDULED,
                operator=operator,
            )
            self._windows[window.window_id] = window
            self._history.append(window)
            logger.info("Scheduled maintenance window '%s' for '%s'", window.window_id, service_name)
            return window

    def start_maintenance(self, window_id: str) -> Optional[MaintenanceWindow]:
        """Transition a scheduled maintenance window to ACTIVE status."""
        with self._lock:
            window = self._windows.get(window_id)
            if not window or window.state != MaintenanceState.SCHEDULED:
                return None

            active_window = MaintenanceWindow(
                window_id=window.window_id,
                service_name=window.service_name,
                start_time=window.start_time,
                end_time=window.end_time,
                description=window.description,
                state=MaintenanceState.ACTIVE,
                operator=window.operator,
            )
            self._windows[window_id] = active_window
            self._active_services[window.service_name] = window_id
            self._history.append(active_window)
            logger.info("Maintenance STARTED for '%s' (window: %s)", window.service_name, window_id)
            return active_window

    def end_maintenance(self, window_id: str) -> Optional[MaintenanceWindow]:
        """Complete an active maintenance window."""
        with self._lock:
            window = self._windows.get(window_id)
            if not window or window.state != MaintenanceState.ACTIVE:
                return None

            completed_window = MaintenanceWindow(
                window_id=window.window_id,
                service_name=window.service_name,
                start_time=window.start_time,
                end_time=window.end_time,
                description=window.description,
                state=MaintenanceState.COMPLETED,
                operator=window.operator,
            )
            self._windows[window_id] = completed_window
            self._active_services.pop(window.service_name, None)
            self._history.append(completed_window)
            logger.info("Maintenance COMPLETED for '%s' (window: %s)", window.service_name, window_id)
            return completed_window

    def cancel_maintenance(self, window_id: str) -> Optional[MaintenanceWindow]:
        """Cancel a maintenance window."""
        with self._lock:
            window = self._windows.get(window_id)
            if not window:
                return None

            cancelled_window = MaintenanceWindow(
                window_id=window.window_id,
                service_name=window.service_name,
                start_time=window.start_time,
                end_time=window.end_time,
                description=window.description,
                state=MaintenanceState.CANCELLED,
                operator=window.operator,
            )
            self._windows[window_id] = cancelled_window
            self._active_services.pop(window.service_name, None)
            self._history.append(cancelled_window)
            return cancelled_window

    def is_in_maintenance(self, service_name: str, now: Optional[datetime] = None) -> bool:
        """Check if service is currently in maintenance window."""
        with self._lock:
            # Explicit active window check
            if service_name in self._active_services:
                return True

            current_t = now or datetime.now(timezone.utc)
            for window in self._windows.values():
                if window.service_name == service_name:
                    if window.state in (MaintenanceState.SCHEDULED, MaintenanceState.ACTIVE):
                        if window.start_time <= current_t <= window.end_time:
                            return True

            return False

    def get_window(self, window_id: str) -> Optional[MaintenanceWindow]:
        """Get maintenance window details."""
        with self._lock:
            return self._windows.get(window_id)

    def get_windows_for_service(self, service_name: str) -> List[MaintenanceWindow]:
        """Get maintenance windows for service."""
        with self._lock:
            return [w for w in self._windows.values() if w.service_name == service_name]

    def clear(self) -> None:
        """Clear maintenance records."""
        with self._lock:
            self._windows.clear()
            self._active_services.clear()
            self._history.clear()
