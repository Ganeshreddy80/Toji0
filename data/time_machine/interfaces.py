"""Abstract interfaces for historical event-by-event data replay reconstruction."""

from __future__ import annotations

import abc
from datetime import datetime
from typing import Any, Callable


class ITimeMachine(abc.ABC):
    """Core contract for the Time Machine historical reconstruction engine."""

    @property
    @abc.abstractmethod
    def current_time(self) -> datetime:
        """Current virtual timestamp of the simulator/replay."""

    @abc.abstractmethod
    def set_time(self, timestamp: datetime) -> None:
        """Seek simulation time directly to timestamp."""

    @abc.abstractmethod
    def get_historical_snapshot(
        self, symbol: str, data_type: str, timestamp: datetime | None = None
    ) -> Any:
        """Retrieve state/records of symbol as-of virtual timestamp.

        If timestamp is None, the current simulator time is used.
        This guarantees zero look-ahead bias during backtests.
        """

    @abc.abstractmethod
    def replay(
        self,
        start_time: datetime,
        end_time: datetime,
        step_seconds: float,
        callback: Callable[[datetime], None],
    ) -> None:
        """Iterate simulation clock forward step-by-step.

        Fires callback at each increment, allowing strategies to react.
        """
