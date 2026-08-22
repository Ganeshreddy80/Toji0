"""Unit tests for Simulated Broker (Sprint 7A)."""

from __future__ import annotations

import pytest

from backtesting_engine.broker.simulated_broker import SimulatedBroker
from backtesting_engine.core.enums import OrderType, PositionSide, SimulatedOrderStatus, TimeInForce
from backtesting_engine.core.events import SimulatedOrderCancelled, SimulatedOrderPlaced
from backtesting_engine.core.exceptions import SimulatedBrokerError
from toji_platform.core.event_bus import InMemoryEventBus


def test_simulated_broker_place_and_cancel():
    event_bus = InMemoryEventBus()
    placed_events = []
    cancelled_events = []

    event_bus.subscribe(SimulatedOrderPlaced().event_type, lambda e: placed_events.append(e))
    event_bus.subscribe(SimulatedOrderCancelled().event_type, lambda e: cancelled_events.append(e))

    broker = SimulatedBroker(event_bus=event_bus)

    order = broker.place_order(
        symbol="BTC/USDT",
        side=PositionSide.LONG,
        quantity=1.5,
        order_type=OrderType.LIMIT,
        price=50000.0,
    )

    assert order.status == SimulatedOrderStatus.ACCEPTED
    assert order.symbol == "BTC/USDT"
    assert order.quantity == 1.5
    assert len(placed_events) == 1

    cancelled = broker.cancel_order(order.order_id)
    assert cancelled is not None
    assert cancelled.status == SimulatedOrderStatus.CANCELLED
    assert len(cancelled_events) == 1


def test_simulated_broker_validations():
    broker = SimulatedBroker()

    with pytest.raises(SimulatedBrokerError, match="Invalid order parameters"):
        broker.place_order(symbol="", side=PositionSide.LONG, quantity=1.0)

    with pytest.raises(SimulatedBrokerError, match="LIMIT orders require a positive price"):
        broker.place_order(symbol="BTC/USDT", side=PositionSide.LONG, quantity=1.0, order_type=OrderType.LIMIT, price=0.0)

    with pytest.raises(SimulatedBrokerError, match="STOP / STOP_LIMIT orders require a positive stop_price"):
        broker.place_order(symbol="BTC/USDT", side=PositionSide.SHORT, quantity=1.0, order_type=OrderType.STOP, stop_price=0.0)
