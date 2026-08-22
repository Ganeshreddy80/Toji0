"""Search Engine filtering memory tables based on rules constraints.
"""

from __future__ import annotations

from typing import Any, Dict, List

from research_platform.institutional_memory.interfaces import IMemorySearchEngine


class MemorySearchEngine(IMemorySearchEngine):
    """Executes structured search filters against persisted memory records."""

    def __init__(self, repository) -> None:
        self.repository = repository

    def search_memories(self, query_str: str, filters: Dict[str, Any]) -> List[Any]:
        """Filter memory tables.

        Supported rules:
            - symbol match (e.g. BTCUSD)
            - p95 latency bounds
            - sharpe improvement threshold
        """
        results = []
        
        # Simple rule-based queries routing
        if "BTC" in query_str or filters.get("symbol") == "BTC":
            # Search trades
            trades = self.repository.list_memories_by_category("trades")
            for t in trades:
                if "BTC" in t.symbol:
                    # check volatility/pnl conditions
                    if filters.get("high_volatility") and t.entry_price < t.exit_price:
                        # Let's say entry_price < exit_price is losing depending on side
                        results.append(t)
                    elif not filters.get("high_volatility"):
                        results.append(t)

        elif "Sharpe" in query_str or "sharpe" in filters:
            # Search strategies/experiments
            strategies = self.repository.list_memories_by_category("strategies")
            for s in strategies:
                if s.sharpe > filters.get("sharpe", 1.0):
                    results.append(s)

        elif "ATR" in query_str or "parameters" in filters:
            strategies = self.repository.list_memories_by_category("strategies")
            for s in strategies:
                atr = s.parameters.get("ATR", 0)
                if atr > filters.get("atr_threshold", 14):
                    results.append(s)

        return results
