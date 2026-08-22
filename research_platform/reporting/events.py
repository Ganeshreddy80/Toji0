"""Domain events for Institutional Reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class ReportGenerated(BaseEvent):
    """Fired when an institutional report gets generated."""
    pass
