from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from toji_platform.core.types import HealthStatus
from execution_engine.brokers.broker_interface import IBrokerAdapter
from execution_engine.core.exceptions import BrokerError
from execution_engine.core.models import Order
from execution_engine.core.enums import OrderState, OrderSide, OrderType, OrderTimeInForce
from execution_engine.brokers.capabilities import BrokerCapabilities
from market_gateway.providers.binance.exchange import BinanceExchangeProvider

logger = logging.getLogger("toji.binance_broker")


class BinanceBroker(IBrokerAdapter):
    """Binance Spot Broker Adapter that routes orders to the BinanceExchangeProvider."""

    def __init__(self, config_settings: dict[str, Any]) -> None:
        self._config = config_settings
        self._container = config_settings.get("container")
        self._connected = False
        self._provider: Optional[BinanceExchangeProvider] = None

    def _get_provider(self) -> BinanceExchangeProvider:
        if self._provider is None:
            if self._container is None or not self._container.has(BinanceExchangeProvider):
                raise BrokerError("BinanceExchangeProvider not registered in DI container.")
            self._provider = self._container.resolve(BinanceExchangeProvider)
        return self._provider

    def get_capabilities(self) -> BrokerCapabilities:
        """Introspect broker advanced execution features and limits."""
        return BrokerCapabilities(
            supports_market=True,
            supports_limit=True,
            supports_stop=True,
            supports_trailing_stop=True,
            supports_reduce_only=True,
            supports_post_only=True,
            supports_oco=True,
            supports_iceberg=True,
            supports_brackets=False,
            supports_twap=False,
            supports_vwap=False,
            max_leverage=125.0,
            precision=8,
            tick_size=0.00000001,
            min_notional=10.0,
        )

    def connect(self) -> None:
        try:
            p = self._get_provider()
            p.connect()
            self._connected = True
        except Exception as e:
            logger.error("Failed to connect BinanceBroker: %s", e)
            self._connected = False

    def disconnect(self) -> None:
        if self._provider is not None:
            try:
                self._provider.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting Binance provider: %s", e)
        elif self._container is not None and self._container.has(BinanceExchangeProvider):
            try:
                p = self._get_provider()
                p.disconnect()
            except Exception as e:
                logger.warning("Error disconnecting Binance provider: %s", e)
        self._connected = False

    def health(self) -> HealthStatus:
        if not self._connected:
            return HealthStatus.UNHEALTHY
        try:
            p = self._get_provider()
            p_health = p.health()
            status = p_health.get("status", "disconnected")
            if status == "connected":
                return HealthStatus.HEALTHY
            elif status == "reconnecting":
                return HealthStatus.DEGRADED
        except Exception:
            pass
        return HealthStatus.UNHEALTHY

    def submit_order(self, order: Order) -> Order:
        """Submit the order to Binance Spot Demo Exchange."""
        p = self._get_provider()
        side_str = "BUY" if order.side == OrderSide.BUY else "SELL"
        symbol = order.symbol.replace("/", "")  # Convert base/quote to basequote format

        try:
            if order.order_type == OrderType.MARKET:
                res = p.place_market_order(symbol, side_str, order.quantity)
            elif order.order_type == OrderType.LIMIT:
                if order.price is None:
                    raise BrokerError("Limit price is required for LIMIT orders.")
                res = p.place_limit_order(symbol, side_str, order.quantity, order.price)
            else:
                raise BrokerError(f"Unsupported order type in BinanceBroker: {order.order_type}")

            status_str = res.get("status", "NEW")
            order_state = OrderState.SUBMITTED
            filled = 0.0
            avg_price = 0.0

            if status_str == "FILLED":
                order_state = OrderState.FILLED
                filled = float(res.get("executedQty", order.quantity))
                avg_price = float(res.get("price") or 0.0)
                if avg_price == 0.0 and filled > 0:
                    avg_price = float(res.get("cummulativeQuoteQty", 0.0)) / filled
            elif status_str == "CANCELED":
                order_state = OrderState.CANCELLED
            elif status_str == "REJECTED":
                order_state = OrderState.REJECTED

            return order.model_copy(update={
                "broker_order_id": str(res.get("orderId")),
                "state": order_state,
                "filled_quantity": filled,
                "average_fill_price": avg_price if avg_price > 0 else None,
                "updated_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.error("Failed to submit Binance order %s: %s", order.client_order_id, e)
            return order.model_copy(update={
                "state": OrderState.REJECTED,
                "error_message": str(e),
                "updated_at": datetime.now(timezone.utc),
            })

    def cancel_order(self, client_order_id: str) -> Order:
        # Note: client_order_id is local order id. But Binance cancel needs symbol.
        # So we look it up or cancel via provider. Since we cancel by symbol/client_order_id:
        p = self._get_provider()
        # Find symbol from current orders if possible or assume a default or pass it
        # Wait, since cancel_order in interface takes client_order_id, let's search open orders to find the symbol
        try:
            open_orders = p.get_open_orders()
            symbol = "BTCUSDT"
            for o in open_orders:
                if o.get("clientOrderId") == client_order_id:
                    symbol = o["symbol"]
                    break
            
            res = p.cancel_order(symbol, client_order_id)
            return Order(
                client_order_id=client_order_id,
                execution_id="cancel-req",
                request_id="cancel-req",
                signal_id="cancel-req",
                strategy_id="cancel-req",
                position_id="cancel-req",
                correlation_id="cancel-req",
                broker_order_id=str(res.get("orderId")),
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=float(res.get("origQty", 0.0)),
                time_in_force=OrderTimeInForce.GTC,
                state=OrderState.CANCELLED,
                updated_at=datetime.now(timezone.utc)
            )
        except Exception as e:
            logger.error("Failed to cancel Binance order %s: %s", client_order_id, e)
            raise BrokerError(f"Failed to cancel order: {e}")

    def modify_order(self, client_order_id: str, quantity: float, price: float) -> Order:
        raise BrokerError("BinanceBroker: Modify order is not supported on Binance Spot API.")

    def get_order(self, client_order_id: str) -> Order:
        # Query open orders
        p = self._get_provider()
        try:
            open_orders = p.get_open_orders()
            for o in open_orders:
                if o.get("clientOrderId") == client_order_id:
                    return Order(
                        client_order_id=client_order_id,
                        execution_id="query",
                        request_id="query",
                        signal_id="query",
                        strategy_id="query",
                        position_id="query",
                        correlation_id="query",
                        broker_order_id=str(o.get("orderId")),
                        symbol=o["symbol"],
                        side=OrderSide.BUY if o["side"] == "BUY" else OrderSide.SELL,
                        order_type=OrderType.LIMIT if o["type"] == "LIMIT" else OrderType.MARKET,
                        quantity=float(o["origQty"]),
                        price=float(o.get("price", 0.0)) or None,
                        time_in_force=OrderTimeInForce.GTC,
                        state=OrderState.SUBMITTED,
                        filled_quantity=float(o.get("executedQty", 0.0)),
                        updated_at=datetime.now(timezone.utc)
                    )
            raise BrokerError(f"Order {client_order_id} not found in open orders.")
        except Exception as e:
            raise BrokerError(f"Get order failed: {e}")

    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        p = self._get_provider()
        try:
            raw_orders = p.get_open_orders(symbol)
            orders = []
            for o in raw_orders:
                orders.append(Order(
                    client_order_id=o.get("clientOrderId", ""),
                    execution_id="query",
                    request_id="query",
                    signal_id="query",
                    strategy_id="query",
                    position_id="query",
                    correlation_id="query",
                    broker_order_id=str(o.get("orderId")),
                    symbol=o["symbol"],
                    side=OrderSide.BUY if o["side"] == "BUY" else OrderSide.SELL,
                    order_type=OrderType.LIMIT if o["type"] == "LIMIT" else OrderType.MARKET,
                    quantity=float(o["origQty"]),
                    price=float(o.get("price", 0.0)) or None,
                    time_in_force=OrderTimeInForce.GTC,
                    state=OrderState.SUBMITTED,
                    filled_quantity=float(o.get("executedQty", 0.0)),
                    updated_at=datetime.now(timezone.utc)
                ))
            return orders
        except Exception as e:
            logger.error("Failed to get open orders: %s", e)
            return []

    def get_positions(self) -> List[Any]:
        p = self._get_provider()
        try:
            return p.get_positions()
        except Exception as e:
            logger.error("Failed to get positions: %s", e)
            return []

    def get_balance(self) -> dict[str, float]:
        p = self._get_provider()
        try:
            return p.get_balances()
        except Exception as e:
            logger.error("Failed to get balances: %s", e)
            return {"USDT": 0.0}

    def ping(self) -> bool:
        try:
            p = self._get_provider()
            return p.ping()
        except Exception:
            return False
