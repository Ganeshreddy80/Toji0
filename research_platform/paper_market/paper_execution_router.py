"""Execution router implementing dynamic routing (Simulation -> Paper -> Live).
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from research_platform.paper_market.interfaces import IPaperExecutionRouter

logger = logging.getLogger(__name__)


class PaperExecutionRouter(IPaperExecutionRouter):
    """Abstraction routing order requests based on the configured mode."""

    def __init__(self, container: Any, default_mode: str = "PAPER") -> None:
        self._container = container
        self._mode = default_mode  # SIMULATION, PAPER, or LIVE

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode not in ("SIMULATION", "PAPER", "LIVE"):
            raise ValueError(f"Invalid execution mode '{mode}'")
        self._mode = mode
        logger.info("Execution Router: Mode set to '%s'", mode)

    def route_order(
        self,
        strategy_id: str,
        symbol: str,
        quantity: float,
        price: float,
        order_type: str,
        side: str,
        rationale: str
    ) -> Any:
        """Route trade requests to target execution engine engines."""
        if self._mode == "SIMULATION":
            # Simulation maps back to Backtesting Engine
            if self._container.has("research_platform.backtesting_engine.orchestrator.BacktestingEngineOrchestrator"):
                backtester = self._container.resolve("research_platform.backtesting_engine.orchestrator.BacktestingEngineOrchestrator")
                return backtester.submit_order(strategy_id, symbol, quantity, price, order_type, side)
            else:
                # Fallback simple simulator
                logger.info("Simulation order routed internally for %s", symbol)
                return {"status": "FILLED", "mode": "SIMULATION"}

        elif self._mode == "PAPER":
            # Paper execution maps directly to PaperTradingOrchestrator (R28)
            p_orch_key = "research_platform.paper_trading.orchestrator.PaperTradingOrchestrator"
            if self._container.has(p_orch_key):
                paper_orch = self._container.resolve(p_orch_key)
                return paper_orch.submit_paper_order(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    quantity=quantity,
                    price=price,
                    order_type=order_type,
                    side=side,
                    rationale=rationale
                )
            else:
                raise RuntimeError("PaperTradingOrchestrator registry not found in DI container.")

        elif self._mode == "LIVE":
            raise PermissionError(
                "LIVE execution is intentionally disabled in this deployment phase. "
                "Only SIMULATION and PAPER sandboxes are certified for execution."
            )

        raise ValueError(f"Unsupported routing mode '{self._mode}'")
