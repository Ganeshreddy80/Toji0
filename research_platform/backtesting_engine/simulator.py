"""Execution Simulator evaluating spread, slippage models, and commissions.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from research_platform.backtesting_engine.interfaces import IExecutionSimulator
from research_platform.backtesting_engine.models import MarketEvent, OrderFill, OrderRequest, SlippageModel, CommissionModel


class ExecutionSimulator(IExecutionSimulator):
    """Applies realistic commission structures and slippage penalties to transactions."""

    def __init__(self, slippage_cfg: SlippageModel, commission_cfg: CommissionModel) -> None:
        self._slippage_cfg = slippage_cfg
        self._commission_cfg = commission_cfg

    def simulate_fill(self, request: OrderRequest, market_data: MarketEvent) -> OrderFill:
        """Apply spread, slippage, and commissions calculations to simulate fills."""
        close_price = market_data.data.get("close", 0.0)
        base_price = market_data.data.get("ask" if request.direction == "BUY" else "bid", close_price)

        # 1. Compute Slippage
        slippage_val = 0.0
        if self._slippage_cfg.type == "Fixed":
            slippage_val = self._slippage_cfg.params.get("amount", 0.01)
        elif self._slippage_cfg.type == "Percentage":
            pct = self._slippage_cfg.params.get("percentage", 0.0005)
            slippage_val = base_price * pct

        if request.direction == "BUY":
            fill_price = base_price + slippage_val
        else:
            fill_price = base_price - slippage_val

        # 2. Compute Commission
        commission = 0.0
        if self._commission_cfg.type == "Fixed":
            commission = self._commission_cfg.params.get("fee", 1.0)
        elif self._commission_cfg.type == "Percentage":
            pct = self._commission_cfg.params.get("percentage", 0.001)
            commission = fill_price * request.quantity * pct

        return OrderFill(
            order_id=request.order_id,
            fill_id=str(uuid.uuid4()),
            symbol=request.symbol,
            quantity=request.quantity,
            price=fill_price,
            commission=commission,
            slippage=slippage_val,
            timestamp=market_data.timestamp
        )
