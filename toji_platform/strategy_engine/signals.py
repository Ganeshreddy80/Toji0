"""Signal definitions."""

from __future__ import annotations
from enum import Enum

class SignalDirection(str, Enum):
    """Execution signal directions."""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
