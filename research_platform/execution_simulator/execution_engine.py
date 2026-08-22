"""Execution simulator engine calculating matched fills, slippage, and fees.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Tuple
from research_platform.execution_simulator.interfaces import ISimulatorExecutionEngine
from research_platform.execution_simulator.models import SimulatedExecution, SimulatedFill
from research_platform.execution_simulator.orderbook_simulator import OrderBookSimulator
from research_platform.execution_simulator.matching_engine import MatchingEngine
from research_platform.execution_simulator.slippage_engine import SlippageEngine
from research_platform.execution_simulator.fee_engine import FeeEngine


class ExecutionEngine(ISimulatorExecutionEngine):
    """Calculates order matching outcomes."""

    def __init__(self) -> None:
        self._book_sim = OrderBookSimulator()
        self._matcher = MatchingEngine()
        self._slippage_eng = SlippageEngine()
        self._fee_eng = FeeEngine()

    def simulate_order_execution(
        self,
        order_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str
    ) -> SimulatedExecution:
        # Generate simulated orderbook slice centered around target price
        mid = price if price > 0.0 else 100.0
        book = self._book_sim.generate_slice(mid)
        
        # Match order against levels
        matched_fills = self._matcher.match_against_book(book, quantity, side)
        
        if not matched_fills:
            # Fallback fill
            matched_fills = [(mid, quantity)]

        fills = [SimulatedFill(price=p, quantity=q) for p, q in matched_fills]
        
        # Calculate statistics
        total_qty = sum(q for _, q in matched_fills)
        avg_price = sum(p * q for p, q in matched_fills) / total_qty
        
        slippage = self._slippage_eng.calculate_slippage(quantity)
        fees = self._fee_eng.calculate_fees(total_qty * avg_price)

        return SimulatedExecution(
            execution_id=f"sim-exec-{uuid.uuid4().hex[:8]}",
            order_id=order_id,
            fills=fills,
            average_price=avg_price,
            slippage=slippage,
            fees=fees,
            status="FILLED"
        )
