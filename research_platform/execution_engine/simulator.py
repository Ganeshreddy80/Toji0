"""Exchange Execution Simulator — top-level entry point.

Orchestrates FillEngine + ExchangeFaultSimulator to produce realistic
order fills.  Call simulate_order() from the paper trading runner.
"""

from __future__ import annotations

import uuid
from typing import Optional, Dict, Any

from research_platform.execution_engine.simulator_models import SimulatedFill, OrderStatus
from research_platform.execution_engine.fill_engine import FillEngine
from research_platform.execution_engine.exchange_faults import (
    ExchangeFaultSimulator,
    FaultType,
)
from research_platform.execution_engine.execution_report import ExecutionAnalytics
from research_platform.execution_engine.liquidity import LiquidityEngine
import logging

logger = logging.getLogger(__name__)


class ExchangeExecutionSimulator:
    """High-level simulator coordinating fills, faults, and quality reports."""

    def __init__(
        self,
        spread_bps: float = 6.0,
        maker_fee: float = 0.0002,
        taker_fee: float = 0.0005,
        max_volume_pct: float = 0.20,
        fault_probability: float = 0.0,
        fault_seed: Optional[int] = None,
    ) -> None:
        self.fill_engine = FillEngine(
            spread_bps=spread_bps,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            max_volume_pct=max_volume_pct,
        )
        self.fault_sim = ExchangeFaultSimulator(
            fault_probability=fault_probability,
            seed=fault_seed,
        )
        self.analytics = ExecutionAnalytics()
        self.liquidity_engine = LiquidityEngine(max_volume_pct=max_volume_pct)

    def simulate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        mid_price: float,
        market_volume: float,
        atr: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        expected_entry: Optional[float] = None,
        order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulate order lifecycle and return fill + quality report dict.

        Args:
            order_type: "MARKET" or "LIMIT"
            limit_price: Required when order_type=="LIMIT"
            expected_entry: Signal price at decision time (defaults to mid_price)
        """
        order_id = order_id or str(uuid.uuid4())
        expected_entry = expected_entry or mid_price

        # 1. Check for exchange-level fault
        fault = self.fault_sim.maybe_inject_fault()
        if fault.triggered:
            logger.warning("Exchange fault injected: %s — %s", fault.fault_type.value, fault.message)
            rejected = SimulatedFill(
                order_id=order_id,
                symbol=symbol,
                side=side.upper(),
                expected_price=expected_entry,
                fill_price=mid_price,
                quantity=quantity,
                quantity_filled=0.0,
                status=OrderStatus.REJECTED,
                maker_fee=self.fill_engine.maker_fee,
                taker_fee=self.fill_engine.taker_fee,
                fee_paid=0.0,
                slippage=0.0,
                slippage_cost=0.0,
                after_fee_pnl=0.0,
                notes=f"{fault.fault_type.value}: {fault.message}",
            )
            report = self.analytics.generate_report(rejected, liquidity_passed=True, risk_passed=True)
            return {"fill": rejected, "report": report, "fault": fault}

        # 2. Liquidity pre-check (also inside fill_engine, exposed here for transparency)
        liq = self.liquidity_engine.check_liquidity(quantity, market_volume)

        # 3. Execute fill
        if order_type.upper() == "LIMIT" and limit_price is not None:
            fill = self.fill_engine.fill_limit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                current_market_price=mid_price,
                market_volume=market_volume,
                atr=atr,
                expected_entry=expected_entry,
                order_id=order_id,
            )
        else:
            fill = self.fill_engine.fill_market_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                mid_price=mid_price,
                market_volume=market_volume,
                atr=atr,
                expected_entry=expected_entry,
                order_id=order_id,
            )

        # 4. Quality report
        report = self.analytics.generate_report(fill, liquidity_passed=liq.passed, risk_passed=True)

        logger.info(
            "[EXEC] %s %s %.4f @ %.2f | score=%.0f | slip=%.2f | fee=%.4f",
            side.upper(), symbol, quantity, fill.fill_price,
            report.execution_score, fill.slippage, fill.fee_paid,
        )

        return {"fill": fill, "report": report, "fault": None}
