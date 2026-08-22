"""Router selectors mapping target exchange adapters.
"""

from __future__ import annotations

from typing import Dict

from research_platform.execution_engine.adapter import MockExchangeAdapter
from research_platform.execution_engine.interfaces import IExchangeAdapter


class ExchangeRouter:
    """Selects the correct exchange adapter instance for a target order."""

    def __init__(self) -> None:
        self._adapters: Dict[str, IExchangeAdapter] = {
            "BINANCE": MockExchangeAdapter("BINANCE"),
            "COINBASE": MockExchangeAdapter("COINBASE")
        }

    def get_adapter(self, exchange: str) -> IExchangeAdapter:
        """Resolve adapter for exchange."""
        target = exchange.upper()
        if target not in self._adapters:
            # Fallback
            self._adapters[target] = MockExchangeAdapter(target)
        return self._adapters[target]
