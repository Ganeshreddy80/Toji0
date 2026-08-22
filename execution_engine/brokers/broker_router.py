from __future__ import annotations

from typing import Dict

from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.core.exceptions import BrokerError


class BrokerRouter:
    """Resolves and routes execution requests to the selected broker adapter instance."""

    def __init__(self) -> None:
        self._adapters: Dict[str, IBrokerAdapter] = {}

    def register_adapter(self, broker_id: str, adapter: IBrokerAdapter) -> None:
        """Register a broker adapter mapped to an identifier key."""
        self._adapters[broker_id.lower()] = adapter

    def get_adapter(self, broker_id: str) -> IBrokerAdapter:
        """Fetch the active broker adapter instance.

        Raises:
            BrokerError: If the requested adapter has not been registered.
        """
        key = broker_id.lower()
        if key not in self._adapters:
            raise BrokerError(f"No registered broker adapter found for ID '{broker_id}'.")
        return self._adapters[key]
