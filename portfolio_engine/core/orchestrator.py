from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus.interfaces import IEventBus
from toji_platform.core.dependency_injection.interfaces import IContainer
from portfolio_engine.core.enums import PositionSide, PositionState
from portfolio_engine.core.models import Position, ClosedPosition, PortfolioSnapshot
from portfolio_engine.core.state import PortfolioStateStore
from portfolio_engine.core.repository import PortfolioRepository
from portfolio_engine.core.events import (
    PositionOpened,
    PositionUpdated,
    PositionClosed,
    PortfolioUpdated,
    PnlUpdated,
    ExposureUpdated,
)

logger = logging.getLogger(__name__)


class PortfolioOrchestrator:
    """Subscribes to execution events and aggregates position/portfolio updates."""

    def __init__(self) -> None:
        self._state_store: Optional[PortfolioStateStore] = None
        self._repository: Optional[PortfolioRepository] = None
        self._event_bus: Optional[IEventBus] = None
        self._container: Optional[IContainer] = None

    def initialize(
        self,
        state_store: PortfolioStateStore,
        repository: PortfolioRepository,
        event_bus: IEventBus,
        container: Optional[IContainer] = None,
    ) -> None:
        """Initialize service dependencies."""
        self._state_store = state_store
        self._repository = repository
        self._event_bus = event_bus
        self._container = container
        logger.info("PortfolioOrchestrator: Subsystem initialized successfully.")

    def on_execution_completed(self, event: Any) -> None:
        """Handle system.execution_completed events containing finished ExecutionResult."""
        logger.info("PortfolioOrchestrator: Received execution completed event.")
        if not event or not hasattr(event, "payload") or not event.payload:
            return

        payload = event.payload
        orders = payload.get("orders", [])
        for ord_dict in orders:
            self._process_order_dict(ord_dict)

    def on_execution_partial_fill(self, event: Any) -> None:
        """Handle system.execution_partial_fill events carrying single Order details."""
        logger.info("PortfolioOrchestrator: Received partial fill event.")
        if not event or not hasattr(event, "payload") or not event.payload:
            return
        self._process_order_dict(event.payload)

    def on_execution_cancelled(self, event: Any) -> None:
        """Handle system.execution_cancelled events carrying cancelled Order details."""
        logger.info("PortfolioOrchestrator: Received execution cancelled event.")
        if not event or not hasattr(event, "payload") or not event.payload:
            return
        # A cancelled event typically does not add new fills, but we check if it has partial fills
        self._process_order_dict(event.payload)

    def update_price(self, symbol: str, price: float) -> None:
        """Update price feed dynamically for unrealized PnL evaluation."""
        if not self._state_store:
            return
        snap = self._state_store.update_market_price(symbol, price)
        self._repository.save_snapshot(snap)
        self._broadcast_portfolio_updates(snap, symbol, "all")

    def _process_order_dict(self, ord_dict: Dict[str, Any]) -> None:
        """Extract trade details from order dictionary and submit to state store."""
        if not self._state_store:
            return

        filled_qty = float(ord_dict.get("filled_quantity", 0.0))
        if filled_qty <= 0.0:
            return

        symbol = ord_dict.get("symbol", "").upper()
        side_str = ord_dict.get("side", "")
        price = float(ord_dict.get("average_fill_price") or ord_dict.get("price") or 0.0)
        if price <= 0.0:
            return

        # Map side
        side = PositionSide.LONG if "BUY" in str(side_str).upper() else PositionSide.SHORT
        
        position_id = ord_dict.get("position_id") or f"pos-{symbol}-{int(datetime.now(timezone.utc).timestamp())}"
        leverage = float(ord_dict.get("leverage", 1.0))
        margin_required = float(ord_dict.get("margin_required", 0.0))
        
        # Simple mocked commission 0.05% of notional value
        commission = filled_qty * price * 0.0005

        snap, opened, closed = self._state_store.apply_position_fill(
            position_id=position_id,
            symbol=symbol,
            side=side,
            quantity=filled_qty,
            price=price,
            leverage=leverage,
            margin_required=margin_required,
            fees=commission,
        )

        # Save to repository
        self._repository.save_snapshot(snap)
        if opened:
            self._repository.save_position(opened)
            # Publish PositionOpened event
            self._event_bus.publish(
                PositionOpened(
                    payload={
                        "symbol": symbol,
                        "timeframe": "all",
                        "position": opened.model_dump(mode="json"),
                    }
                )
            )
        elif closed:
            self._repository.save_closed_position(closed)
            # Publish PositionClosed event
            self._event_bus.publish(
                PositionClosed(
                    payload={
                        "symbol": symbol,
                        "timeframe": "all",
                        "position": closed.model_dump(mode="json"),
                    }
                )
            )
        else:
            # Publish PositionUpdated event
            pos = self._state_store._position_store.get_position(symbol)
            if pos:
                self._event_bus.publish(
                    PositionUpdated(
                        payload={
                            "symbol": symbol,
                            "timeframe": "all",
                            "position": pos.model_dump(mode="json"),
                        }
                    )
                )

        # Broadcast state changes downstream
        self._broadcast_portfolio_updates(snap, symbol, "all")

    def _broadcast_portfolio_updates(
        self, snap: PortfolioSnapshot, symbol: str, timeframe: str
    ) -> None:
        """Broadcast state updates to the Platform Event Bus."""
        # 1. system.portfolio_updated
        self._event_bus.publish(
            PortfolioUpdated(
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "portfolio": snap.model_dump(mode="json"),
                }
            )
        )
        
        # 2. system.pnl_updated
        self._event_bus.publish(
            PnlUpdated(
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "total_realized_pnl": snap.metrics.total_realized_pnl,
                    "total_unrealized_pnl": snap.metrics.total_unrealized_pnl,
                }
            )
        )

        # 3. system.exposure_updated
        self._event_bus.publish(
            ExposureUpdated(
                payload={
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "gross_exposure": snap.metrics.gross_exposure,
                    "net_exposure": snap.metrics.net_exposure,
                }
            )
        )
