"""Exchange Fault Simulator — models API timeouts, rate-limits, and connection drops.

All faults cause OMS to fail-closed (REJECTED status) so no position is
opened without a confirmed fill.
"""

from __future__ import annotations

import random
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class FaultType(str, Enum):
    API_TIMEOUT = "API_TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    CONNECTION_LOST = "CONNECTION_LOST"
    ORDER_REJECTED = "ORDER_REJECTED"
    NONE = "NONE"


@dataclass
class FaultEvent:
    fault_type: FaultType
    triggered: bool
    message: str
    retry_after_seconds: int = 0   # advisory back-off


class ExchangeFaultSimulator:
    """Randomly injects exchange-level faults to validate OMS fail-closed behaviour.

    Args:
        fault_probability:  Probability (0–1) that any given order call encounters a fault.
        seed:               Optional RNG seed for deterministic tests.
    """

    _FAULT_MESSAGES = {
        FaultType.API_TIMEOUT:     "Exchange API did not respond within timeout window.",
        FaultType.RATE_LIMIT:      "Exchange rate limit exceeded — back off and retry.",
        FaultType.CONNECTION_LOST: "WebSocket connection to exchange was lost.",
        FaultType.ORDER_REJECTED:  "Exchange rejected order: insufficient margin / unknown symbol.",
    }

    _FAULT_WEIGHTS = [30, 20, 20, 30]   # relative probability for each fault type

    def __init__(
        self,
        fault_probability: float = 0.0,
        seed: Optional[int] = None,
    ) -> None:
        self.fault_probability = max(0.0, min(1.0, fault_probability))
        self._rng = random.Random(seed)

    def maybe_inject_fault(self) -> FaultEvent:
        """Roll for a fault.  Returns a FaultEvent — caller must check *.triggered*."""
        if self._rng.random() >= self.fault_probability:
            return FaultEvent(fault_type=FaultType.NONE, triggered=False, message="")

        fault_types = [
            FaultType.API_TIMEOUT,
            FaultType.RATE_LIMIT,
            FaultType.CONNECTION_LOST,
            FaultType.ORDER_REJECTED,
        ]
        chosen = self._rng.choices(fault_types, weights=self._FAULT_WEIGHTS, k=1)[0]

        retry_seconds = {
            FaultType.API_TIMEOUT: 5,
            FaultType.RATE_LIMIT: 60,
            FaultType.CONNECTION_LOST: 10,
            FaultType.ORDER_REJECTED: 0,
        }.get(chosen, 0)

        return FaultEvent(
            fault_type=chosen,
            triggered=True,
            message=self._FAULT_MESSAGES[chosen],
            retry_after_seconds=retry_seconds,
        )

    def force_fault(self, fault_type: FaultType) -> FaultEvent:
        """Deterministically inject a specific fault — useful for unit tests."""
        return FaultEvent(
            fault_type=fault_type,
            triggered=True,
            message=self._FAULT_MESSAGES.get(fault_type, "Unknown fault"),
            retry_after_seconds=0,
        )
