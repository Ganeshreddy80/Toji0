"""Binance Demo Spot Exchange Provider.

Implements REST and WS streams for market data, order routing, balance sync,
and websocket connection recovery with backoff.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import httpx
import websockets

from data.schemas.market_data import OHLCV, OrderBookSnapshot, Trade
from market_gateway.normalizer.normalizer import MarketDataNormalizer
from market_gateway.providers.base import BaseGatewayProvider
from market_gateway.providers.binance.config import BinanceEndpointConfig
from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import (
    AccountUpdated,
    BalanceUpdated,
    ConnectionLost,
    ConnectionRecovered,
    HeartbeatUpdated,
    LatencyMeasured,
    MarketTickReceived,
    OrderBookUpdated,
    PositionUpdated,
    TradeExecuted,
)

logger = logging.getLogger("toji.binance_provider")


class BinanceExchangeProvider(BaseGatewayProvider):
    """Binance Spot Demo Exchange Provider.

    Provides REST execution/account sync and WS streams for paper trading.
    """

    def __init__(self, use_mock: bool = True) -> None:
        super().__init__()
        self._name = "Binance"
        self.use_mock = use_mock
        
        # Security credentials loaded from env vars
        self._api_key = os.getenv("BINANCE_API_KEY", "")
        self._api_secret = os.getenv("BINANCE_API_SECRET", "")

        # Load from canonical endpoint config model
        market_provider = os.getenv("MARKET_PROVIDER", "demo")
        self.endpoint_config = BinanceEndpointConfig.from_provider(market_provider)
        self._rest_url = self.endpoint_config.rest_url.rstrip("/")
        self._ws_url = self.endpoint_config.ws_url.rstrip("/")

        # Subscriptions
        self._candle_subs: dict[tuple[str, str], list[Callable[[OHLCV], None]]] = {}
        self._trade_subs: dict[str, list[Callable[[Trade], None]]] = {}
        self._depth_subs: dict[str, list[Callable[[OrderBookSnapshot], None]]] = {}
        
        self._ticker_subs: set[str] = set()
        self._user_stream_subs: list[Callable[[dict], None]] = []

        # Connection states
        self._ws_connection: websockets.WebSocketClientProtocol | None = None
        self._user_ws_connection: websockets.WebSocketClientProtocol | None = None
        self._ws_task: asyncio.Task[None] | None = None
        self._user_ws_task: asyncio.Task[None] | None = None
        self._mock_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        
        self._running = False
        self._listen_key: str | None = None
        
        self._reconnect_history: list[str] = []
        self._event_bus: Optional[Any] = None
        self._mock_orders: dict[str, dict] = {}
        self._mock_balances: Dict[str, float] = {"USDT": 100000.0, "BTC": 1.5, "ETH": 10.0}
        self._time_offset_ms = 0
        import threading
        self._subs_lock = threading.RLock()

    # ── DI & Event Bus injection ───────────────────────────────────────

    def set_event_bus(self, event_bus: Any) -> None:
        self._event_bus = event_bus

    # ── Core Lifecycle Methods ──────────────────────────────────────────

    def _do_initialize(self) -> None:
        self._running = True

        try:
            loop = asyncio.get_running_loop()
            self._own_loop = None
            self._own_loop_thread = None
        except RuntimeError:
            # Spawn background loop thread
            import threading
            self._own_loop = asyncio.new_event_loop()
            
            def run_loop(loop_obj):
                asyncio.set_event_loop(loop_obj)
                loop_obj.run_forever()
                
            self._own_loop_thread = threading.Thread(
                target=run_loop, args=(self._own_loop,), daemon=True, name="BinanceWSLoop"
            )
            self._own_loop_thread.start()
            loop = self._own_loop

        self._loop = loop

        if self.use_mock:
            self._status = "connected"
            if loop:
                if self._own_loop:
                    self._mock_task = asyncio.run_coroutine_threadsafe(self._run_mock_stream(), loop)
                else:
                    self._mock_task = loop.create_task(self._run_mock_stream())
            logger.info("BinanceExchangeProvider: initialized in MOCK mode.")
        else:
            self._status = "disconnected"
            # Calculate server clock drift offset
            try:
                server_time = self.get_server_time()
                self._time_offset_ms = server_time - int(time.time() * 1000)
                logger.info("BinanceExchangeProvider: clock sync offset calculated: %d ms", self._time_offset_ms)
            except Exception as e:
                logger.warning("BinanceExchangeProvider: failed to sync clock with Binance server: %s", e)

            if loop:
                if self._own_loop:
                    self._ws_task = asyncio.run_coroutine_threadsafe(self._connect_and_listen(), loop)
                    if os.getenv("TRADING_MODE", "paper").lower() == "live":
                        self._user_ws_task = asyncio.run_coroutine_threadsafe(self._connect_user_stream(), loop)
                    else:
                        self._user_ws_task = None
                else:
                    self._ws_task = loop.create_task(self._connect_and_listen())
                    if os.getenv("TRADING_MODE", "paper").lower() == "live":
                        self._user_ws_task = loop.create_task(self._connect_user_stream())
                    else:
                        self._user_ws_task = None
            logger.info("BinanceExchangeProvider: initialized in LIVE Demo mode.")

    def _do_shutdown(self) -> None:
        self._running = False
        self._status = "disconnected"

        # Cancel tasks
        for task in (self._mock_task, self._ws_task, self._user_ws_task, self._keepalive_task):
            if task:
                try:
                    task.cancel()
                except Exception:
                    pass
        
        self._mock_task = None
        self._ws_task = None
        self._user_ws_task = None
        self._keepalive_task = None

        # Close WS connections safely
        if getattr(self, "_loop", None) is not None:
            for conn in (self._ws_connection, self._user_ws_connection):
                if conn:
                    try:
                        running_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        running_loop = None

                    if running_loop == self._loop:
                        self._loop.create_task(conn.close())
                    else:
                        asyncio.run_coroutine_threadsafe(conn.close(), self._loop)

        # Stop background loop if it was created specifically for this provider
        own_loop = getattr(self, "_own_loop", None)
        if own_loop is not None:
            try:
                own_loop.call_soon_threadsafe(own_loop.stop)
            except Exception:
                pass
            self._own_loop = None
            self._own_loop_thread = None

        self._loop = None
        self._ws_connection = None
        self._user_ws_connection = None
        logger.info("BinanceExchangeProvider: shut down completed.")

    # ── Authenticated Requests & REST Helpers ───────────────────────────

    def _sign_params(self, params: dict[str, Any]) -> str:
        """Compute HMAC-SHA256 signature for parameters."""
        params["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
        query_string = urllib.parse.urlencode(sorted(params.items()))
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return f"{query_string}&signature={signature}"

    def _make_rest_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        signed: bool = False
    ) -> Any:
        """Send authenticated REST request."""
        base_url = self._rest_url.rstrip("/")
        if "api.binance.com" in base_url and not base_url.endswith("/api") and path.startswith("/v3/"):
            url = f"{base_url}/api{path}"
        else:
            url = f"{base_url}{path}"
        headers = {"X-MBX-APIKEY": self._api_key}
        params_dict = dict(params or {})

        if signed:
            query = self._sign_params(params_dict)
            full_url = f"{url}?{query}"
        else:
            query = urllib.parse.urlencode(params_dict)
            full_url = f"{url}?{query}" if query else url

        start_time = time.perf_counter()
        try:
            if method.upper() == "GET":
                resp = httpx.get(full_url, headers=headers, timeout=10.0)
            elif method.upper() == "POST":
                resp = httpx.post(full_url, headers=headers, timeout=10.0)
            elif method.upper() == "PUT":
                resp = httpx.put(full_url, headers=headers, timeout=10.0)
            elif method.upper() == "DELETE":
                resp = httpx.delete(full_url, headers=headers, timeout=10.0)
            else:
                raise ValueError(f"Unsupported method: {method}")

            resp.raise_for_status()
            
            # Record server latency
            latency = (time.perf_counter() - start_time) * 1000.0
            self._latency_ms = latency
            self._publish_event(LatencyMeasured, {"endpoint": path, "latency_ms": latency})
            
            return resp.json()
        except Exception as e:
            logger.error("Binance REST Error (%s %s): %s", method, path, e)
            raise

    # ── Public REST API Methods ────────────────────────────────────────

    def connect(self) -> None:
        self.initialize()

    def disconnect(self) -> None:
        self.shutdown()

    def ping(self) -> bool:
        if self.use_mock:
            return True
        try:
            self._make_rest_request("GET", "/v3/ping")
            return True
        except Exception:
            return False

    def get_server_time(self) -> int:
        if self.use_mock:
            return int(time.time() * 1000)
        res = self._make_rest_request("GET", "/v3/time")
        return res.get("serverTime", 0)

    def get_exchange_info(self) -> dict[str, Any]:
        if self.use_mock:
            return {
                "timezone": "UTC",
                "serverTime": int(time.time() * 1000),
                "symbols": [
                    {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT"},
                    {"symbol": "ETHUSDT", "status": "TRADING", "baseAsset": "ETH", "quoteAsset": "USDT"},
                ]
            }
        return self._make_rest_request("GET", "/v3/exchangeInfo")

    def get_symbols(self) -> list[str]:
        info = self.get_exchange_info()
        return [s["symbol"] for s in info.get("symbols", []) if s.get("status") == "TRADING"]

    def get_historical_candles(
        self, symbol: str, interval: str, start: datetime, end: datetime
    ) -> list[OHLCV]:
        """Fetch historical candles via REST API klines."""
        if self.use_mock:
            # Generate dummy historical data points
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())
            delta = 60  # default 1m in seconds
            if interval == "5m":
                delta = 300
            elif interval == "1h":
                delta = 3600
            elif interval == "1d":
                delta = 86400

            candles = []
            curr = start_ts
            price = 95000.0
            while curr <= end_ts:
                dt = datetime.fromtimestamp(curr, tz=timezone.utc)
                candles.append(OHLCV(
                    symbol=symbol,
                    timestamp=dt,
                    open=price,
                    high=price + random.uniform(50, 150),
                    low=price - random.uniform(50, 150),
                    close=price + random.uniform(-50, 50),
                    volume=random.uniform(1.0, 10.0),
                    interval=interval,
                ))
                curr += delta
            return candles

        # Map datetime to timestamps in ms
        start_ms = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)

        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
            "limit": 1000,
        }

        try:
            data = self._make_rest_request("GET", "/v3/klines", params=params)
            normalized = [
                MarketDataNormalizer.normalize_binance_candle(row, symbol=symbol, interval=interval)
                for row in data
            ]
            return normalized
        except Exception as e:
            logger.error("Failed to fetch historical candles for %s: %s", symbol, e)
            raise

    def get_account(self) -> dict[str, Any]:
        if self.use_mock:
            balances = [{"asset": k, "free": str(v), "locked": "0.0"} for k, v in self._mock_balances.items()]
            return {"makerCommission": 15, "takerCommission": 15, "buyerCommission": 0, "sellerCommission": 0, "canTrade": True, "canWithdraw": True, "canDeposit": True, "updateTime": int(time.time() * 1000), "accountType": "SPOT", "balances": balances}
        return self._make_rest_request("GET", "/v3/account", signed=True)

    def get_balances(self) -> dict[str, float]:
        acct = self.get_account()
        balances = {}
        for b in acct.get("balances", []):
            free = float(b.get("free", 0.0))
            locked = float(b.get("locked", 0.0))
            if free > 0 or locked > 0:
                balances[b["asset"]] = free + locked
        return balances

    def get_positions(self) -> list[dict[str, Any]]:
        # Spot has asset balances, let's map non-zero assets to positions
        acct = self.get_account()
        positions = []
        for b in acct.get("balances", []):
            free = float(b.get("free", 0.0))
            asset = b["asset"]
            if free > 0.0 and asset != "USDT":
                positions.append({
                    "symbol": f"{asset}USDT",
                    "amount": free,
                    "entry_price": 0.0,  # Spot entry is unknown from account endpoint
                })
        return positions

    def get_open_orders(self, symbol: Optional[str] = None) -> list[dict[str, Any]]:
        if self.use_mock:
            return list(self._mock_orders.values())
        params = {"symbol": symbol} if symbol else {}
        return self._make_rest_request("GET", "/v3/openOrders", params=params, signed=True)

    # ── Authenticated Order Execution Methods ──────────────────────────

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict[str, Any]:
        """Place a Spot Market Order."""
        if not self.use_mock:
            import os
            if os.getenv("TRADING_MODE") == "paper":
                raise PermissionError("Production safety breach: Cannot place real order when TRADING_MODE=paper!")
        if self.use_mock:
            order_id = f"mock-order-{random.randint(1000, 9999)}"
            res = {
                "symbol": symbol,
                "orderId": order_id,
                "clientOrderId": f"mock-cli-{random.randint(1000, 9999)}",
                "transactTime": int(time.time() * 1000),
                "price": "0.0",
                "origQty": str(quantity),
                "executedQty": str(quantity),
                "cummulativeQuoteQty": str(quantity * 95000.0),
                "status": "FILLED",
                "side": side,
                "type": "MARKET"
            }
            # Adjust balances
            self._adjust_mock_balances(symbol, side, quantity, 95000.0)
            self._publish_order_event(res)
            return res

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "MARKET",
            "quantity": str(quantity),
        }
        res = self._make_rest_request("POST", "/v3/order", params=params, signed=True)
        self._publish_order_event(res)
        return res

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> dict[str, Any]:
        """Place a Spot Limit Order."""
        if not self.use_mock:
            import os
            if os.getenv("TRADING_MODE") == "paper":
                raise PermissionError("Production safety breach: Cannot place real order when TRADING_MODE=paper!")
        if self.use_mock:
            order_id = f"mock-order-{random.randint(1000, 9999)}"
            res = {
                "symbol": symbol,
                "orderId": order_id,
                "clientOrderId": f"mock-cli-{random.randint(1000, 9999)}",
                "transactTime": int(time.time() * 1000),
                "price": str(price),
                "origQty": str(quantity),
                "executedQty": "0.0",
                "cummulativeQuoteQty": "0.0",
                "status": "NEW",
                "side": side,
                "type": "LIMIT",
                "timeInForce": "GTC"
            }
            self._mock_orders[order_id] = res
            self._publish_order_event(res)
            return res

        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": "LIMIT",
            "quantity": str(quantity),
            "price": str(price),
            "timeInForce": "GTC",
        }
        res = self._make_rest_request("POST", "/v3/order", params=params, signed=True)
        self._publish_order_event(res)
        return res

    def cancel_order(self, symbol: str, client_order_id: str) -> dict[str, Any]:
        """Cancel an active Spot order."""
        if self.use_mock:
            found_id = None
            for oid, o in self._mock_orders.items():
                if o.get("clientOrderId") == client_order_id:
                    found_id = oid
                    break
            if found_id:
                order = self._mock_orders.pop(found_id)
                order["status"] = "CANCELED"
                self._publish_order_event(order)
                return order
            raise ValueError(f"Mock order {client_order_id} not found.")

        params = {
            "symbol": symbol,
            "origClientOrderId": client_order_id,
        }
        res = self._make_rest_request("DELETE", "/v3/order", params=params, signed=True)
        self._publish_order_event(res)
        return res

    def cancel_all_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Cancel all active Spot orders on a symbol."""
        if self.use_mock:
            canceled = []
            for oid in list(self._mock_orders.keys()):
                if self._mock_orders[oid]["symbol"] == symbol:
                    order = self._mock_orders.pop(oid)
                    order["status"] = "CANCELED"
                    canceled.append(order)
                    self._publish_order_event(order)
            return canceled

        params = {"symbol": symbol}
        res = self._make_rest_request("DELETE", "/v3/openOrders", params=params, signed=True)
        return res

    # ── User Stream listenKey Lifecycle ────────────────────────────────

    def _create_listen_key(self) -> str:
        res = self._make_rest_request("POST", "/v3/userDataStream")
        return res.get("listenKey", "")

    def _ping_listen_key(self) -> None:
        if self._listen_key:
            try:
                self._make_rest_request("PUT", "/v3/userDataStream", params={"listenKey": self._listen_key})
            except Exception as e:
                logger.warning("Failed to refresh listenKey: %s", e)

    async def _listen_key_keepalive_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(1200)  # Refresh every 20 minutes
                if self._running:
                    self._ping_listen_key()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Failed to refresh listenKey in keepalive loop: %s", e)

    # ── WebSocket Subscription Operations ───────────────────────────────

    def subscribe_candles(
        self, symbol: str, interval: str, callback: Callable[[OHLCV], None]
    ) -> None:
        key = (symbol, interval)
        with self._subs_lock:
            if key not in self._candle_subs:
                self._candle_subs[key] = []
            self._candle_subs[key].append(callback)
        logger.info("Subscribed to Binance candle feed: %s %s", symbol, interval)
        self._send_subscription_update()

    def subscribe_trades(self, symbol: str, callback: Callable[[Trade], None]) -> None:
        with self._subs_lock:
            if symbol not in self._trade_subs:
                self._trade_subs[symbol] = []
            self._trade_subs[symbol].append(callback)
        logger.info("Subscribed to Binance trade feed: %s", symbol)
        self._send_subscription_update()

    def subscribe_order_book(
        self, symbol: str, callback: Callable[[OrderBookSnapshot], None]
    ) -> None:
        with self._subs_lock:
            if symbol not in self._depth_subs:
                self._depth_subs[symbol] = []
            self._depth_subs[symbol].append(callback)
        logger.info("Subscribed to Binance depth feed: %s", symbol)
        self._send_subscription_update()

    def subscribe_ticker(self, symbol: str) -> None:
        with self._subs_lock:
            self._ticker_subs.add(symbol.upper())
        self._send_subscription_update()

    def subscribe_book(self, symbol: str) -> None:
        self.subscribe_order_book(symbol, lambda ob: None)

    def subscribe_kline(self, symbol: str, interval: str) -> None:
        self.subscribe_candles(symbol, interval, lambda c: None)

    def subscribe_trade_stream(self, symbol: str) -> None:
        self.subscribe_trades(symbol, lambda t: None)

    def subscribe_user_stream(self, callback: Callable[[dict], None]) -> None:
        self._user_stream_subs.append(callback)

    def subscribe_execution_stream(self, callback: Callable[[dict], None]) -> None:
        # Same as user stream (execution report is routed here)
        self.subscribe_user_stream(callback)

    def subscribe_account_stream(self, callback: Callable[[dict], None]) -> None:
        # Same as user stream
        self.subscribe_user_stream(callback)

    def _send_subscription_update(self) -> None:
        """Constructs subscription messages to send over live WS protocol."""
        if self.use_mock or self._ws_connection is None:
            return

        # Prepare subscription streams
        with self._subs_lock:
            streams = []
            for symbol, interval in self._candle_subs.keys():
                streams.append(f"{symbol.lower()}@kline_{interval}")
            for symbol in self._trade_subs.keys():
                streams.append(f"{symbol.lower()}@trade")
            for symbol in self._depth_subs.keys():
                streams.append(f"{symbol.lower()}@depth20@100ms")
            for symbol in self._ticker_subs:
                streams.append(f"{symbol.lower()}@ticker")

        if not streams:
            return

        subscribe_payload = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": random.randint(1, 10000),
        }
        loop = getattr(self, "_loop", None)
        if loop is not None:
            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None

            if running_loop == loop:
                loop.create_task(self._send_ws_message(subscribe_payload))
            else:
                asyncio.run_coroutine_threadsafe(self._send_ws_message(subscribe_payload), loop)
        else:
            try:
                running_loop = asyncio.get_running_loop()
                running_loop.create_task(self._send_ws_message(subscribe_payload))
            except RuntimeError:
                pass

    async def _send_ws_message(self, payload: dict[str, Any]) -> None:
        if self._ws_connection:
            try:
                await self._ws_connection.send(json.dumps(payload))
            except Exception as e:
                logger.error("Failed to send WebSocket message: %s", e)

    # ── WebSocket Connect & Listen Loops ────────────────────────────────

    async def _connect_and_listen(self) -> None:
        """WebSocket loop for public market data streams."""
        backoff = 1.0
        max_backoff = 60.0
        import ssl

        while self._running:
            try:
                logger.info("Connecting to public Binance WebSocket: %s", self._ws_url)
                ssl_context = ssl.create_default_context()
                ws_conn_ctx = None
                
                try:
                    # Attempt connection with default SSL verification
                    ws_conn_ctx = websockets.connect(self._ws_url, ssl=ssl_context)
                    ws = await ws_conn_ctx.__aenter__()
                except (ssl.SSLError, ssl.CertificateError, Exception) as ssl_err:
                    # Fallback to unverified connection if certificate validation fails locally
                    if isinstance(ssl_err, (ssl.SSLError, ssl.CertificateError)) or "certificate verify failed" in str(ssl_err):
                        logger.warning("SSL verification failed. Retrying connection without verification: %s", ssl_err)
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE
                        ws_conn_ctx = websockets.connect(self._ws_url, ssl=ssl_context)
                        ws = await ws_conn_ctx.__aenter__()
                    else:
                        raise ssl_err

                try:
                    self._ws_connection = ws
                    self._status = "connected"
                    self._reconnect_history.append(f"{datetime.now(timezone.utc).isoformat()} - Public WS Connected")
                    self._publish_event(ConnectionRecovered, {"type": "public"})
                    backoff = 1.0

                    self._send_subscription_update()

                    while self._running:
                        try:
                            msg_str = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            msg = json.loads(msg_str)
                            
                            # Latency tracking
                            if "E" in msg:
                                self._latency_ms = (time.time() * 1000.0) - float(msg["E"])
                                self._publish_event(LatencyMeasured, {"endpoint": "WS_public", "latency_ms": self._latency_ms})

                            self._handle_ws_message(msg)
                            self._publish_event(HeartbeatUpdated, {"status": "alive"})
                        except asyncio.TimeoutError:
                            # Send Ping frame to confirm liveness
                            pong = await ws.ping()
                            await asyncio.wait_for(pong, timeout=5.0)
                finally:
                    if ws_conn_ctx:
                        await ws_conn_ctx.__aexit__(None, None, None)
            except Exception as e:
                self._ws_connection = None
                self._status = "disconnected"
                self._reconnect_history.append(f"{datetime.now(timezone.utc).isoformat()} - Public WS Error: {e}")
                self._publish_event(ConnectionLost, {"type": "public", "error": str(e)})
                
                sleep_time = backoff * (2 ** random.uniform(0.0, 0.5))
                backoff = min(backoff * 2.0, max_backoff)
                logger.warning("Binance WS error: %s. Reconnecting in %.2fs...", e, sleep_time)
                await asyncio.sleep(sleep_time)

    async def _connect_user_stream(self) -> None:
        """WebSocket loop for private user data stream."""
        backoff = 1.0
        max_backoff = 60.0

        while self._running:
            try:
                self._listen_key = self._create_listen_key()
                user_ws_url = f"{self._ws_url}/{self._listen_key}"
                logger.info("Connecting to private Binance User Stream: %s", user_ws_url)

                # Start keepalive task
                if self._keepalive_task:
                    self._keepalive_task.cancel()
                self._keepalive_task = asyncio.create_task(self._listen_key_keepalive_loop())

                async with websockets.connect(user_ws_url) as ws:
                    self._user_ws_connection = ws
                    self._publish_event(ConnectionRecovered, {"type": "user"})
                    backoff = 1.0

                    while self._running:
                        try:
                            msg_str = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            msg = json.loads(msg_str)
                            self._handle_user_ws_message(msg)
                        except asyncio.TimeoutError:
                            pong = await ws.ping()
                            await asyncio.wait_for(pong, timeout=5.0)
            except Exception as e:
                self._user_ws_connection = None
                self._publish_event(ConnectionLost, {"type": "user", "error": str(e)})
                
                sleep_time = backoff * (2 ** random.uniform(0.0, 0.5))
                backoff = min(backoff * 2.0, max_backoff)
                logger.warning("Binance User WS error: %s. Reconnecting in %.2fs...", e, sleep_time)
                await asyncio.sleep(sleep_time)

    # ── Handle Incoming Messages ───────────────────────────────────────

    def _handle_ws_message(self, msg: dict[str, Any]) -> None:
        """Parse incoming public market data messages and dispatch to event bus."""
        event_type = msg.get("e")
        symbol = msg.get("s", "")
        
        self._publish_event(MarketTickReceived, msg)

        with self._subs_lock:
            if event_type == "kline":
                interval = msg["k"]["i"]
                if (symbol, interval) in self._candle_subs:
                    candle = MarketDataNormalizer.normalize_binance_candle(msg)
                    callbacks = list(self._candle_subs[(symbol, interval)])
                else:
                    callbacks = []
            elif event_type == "trade":
                if symbol in self._trade_subs:
                    trade = MarketDataNormalizer.normalize_binance_trade(msg)
                    callbacks = list(self._trade_subs[symbol])
                else:
                    callbacks = []
            elif "bids" in msg or "b" in msg or "asks" in msg or "a" in msg:
                self._publish_event(OrderBookUpdated, msg)
                if symbol in self._depth_subs:
                    depth = MarketDataNormalizer.normalize_binance_order_book(msg, symbol=symbol)
                    callbacks = list(self._depth_subs[symbol])
                else:
                    callbacks = []
            else:
                callbacks = []

        for cb in callbacks:
            try:
                if event_type == "kline":
                    cb(candle)
                elif event_type == "trade":
                    cb(trade)
                else:
                    cb(depth)
            except Exception as e:
                logger.error("Error executing subscriber callback: %s", e)

    def _handle_user_ws_message(self, msg: dict[str, Any]) -> None:
        """Parse private user stream execution and balance messages."""
        event_type = msg.get("e")
        
        # Route to subscribers
        for cb in self._user_stream_subs:
            try:
                cb(msg)
            except Exception as e:
                logger.error("User WS subscriber callback error: %s", e)

        if event_type == "outboundAccountPosition":
            self._publish_event(AccountUpdated, msg)
            for b in msg.get("B", []):
                asset = b.get("a", "")
                free = float(b.get("f", 0.0))
                self._publish_event(BalanceUpdated, {"asset": asset, "free": free})
        elif event_type == "balanceUpdate":
            self._publish_event(BalanceUpdated, {"asset": msg.get("a"), "delta": float(msg.get("d", 0.0))})
        elif event_type == "executionReport":
            self._publish_event(TradeExecuted, msg)
            # Route fills/updates to ExecutionCompleted
            status = msg.get("X")
            if status in ("FILLED", "CANCELED", "REJECTED"):
                self._publish_event(TradeExecuted, {
                    "symbol": msg.get("s"),
                    "orderId": msg.get("i"),
                    "clientOrderId": msg.get("c"),
                    "price": msg.get("p"),
                    "quantity": msg.get("q"),
                    "status": status,
                })

    # ── Event Bus Publishing Helper ────────────────────────────────────

    def _publish_event(self, event_class: Any, payload: dict) -> None:
        if self._event_bus:
            try:
                event = event_class(source="binance_exchange", payload=payload)
                self._event_bus.publish(event)
            except Exception as e:
                logger.error("Failed to publish event %s: %s", event_class.__name__, e)

    # ── Sandbox Simulation Helper (Mock Stream) ───────────────────────

    async def _run_mock_stream(self) -> None:
        """Mock stream simulating public and user WebSocket events."""
        prices = {"BTCUSDT": 95000.0, "ETHUSDT": 3000.0}

        while self._running:
            self._last_heartbeat = datetime.now(timezone.utc)
            self._last_update = datetime.now(timezone.utc)

            # Update prices for each active symbol
            for symbol in list(self._candle_subs.keys()):
                sym = symbol[0]
                if sym not in prices:
                    prices[sym] = 95000.0 if "BTC" in sym else 3000.0
                prices[sym] += random.uniform(-15.0, 15.0) if "BTC" in sym else random.uniform(-1.0, 1.0)
            for symbol in list(self._trade_subs.keys()):
                if symbol not in prices:
                    prices[symbol] = 95000.0 if "BTC" in symbol else 3000.0
                prices[symbol] += random.uniform(-15.0, 15.0) if "BTC" in symbol else random.uniform(-1.0, 1.0)
            for symbol in list(self._depth_subs.keys()):
                if symbol not in prices:
                    prices[symbol] = 95000.0 if "BTC" in symbol else 3000.0
                prices[symbol] += random.uniform(-15.0, 15.0) if "BTC" in symbol else random.uniform(-1.0, 1.0)

            # Public updates
            for (symbol, interval), callbacks in list(self._candle_subs.items()):
                sym_price = prices.get(symbol, 95000.0 if "BTC" in symbol else 3000.0)
                mock_msg = {
                    "e": "kline",
                    "E": int(time.time() * 1000),
                    "s": symbol,
                    "k": {
                        "t": int(time.time() // 60 * 60 * 1000),
                        "T": int(time.time() // 60 * 60 * 1000 + 59999),
                        "s": symbol,
                        "i": interval,
                        "o": str(sym_price - 2.0),
                        "c": str(sym_price),
                        "h": str(sym_price + 5.0),
                        "l": str(sym_price - 5.0),
                        "v": "1.25",
                        "n": 20,
                        "x": False,
                    }
                }
                candle = MarketDataNormalizer.normalize_binance_candle(mock_msg)
                for cb in callbacks:
                    cb(candle)

            for symbol in list(self._trade_subs.keys()):
                sym_price = prices.get(symbol, 95000.0 if "BTC" in symbol else 3000.0)
                mock_msg = {
                    "e": "trade",
                    "E": int(time.time() * 1000),
                    "T": int(time.time() * 1000),
                    "t": random.randint(100000, 999999),
                    "s": symbol,
                    "p": str(sym_price),
                    "q": "0.1",
                    "m": True,
                }
                trade = MarketDataNormalizer.normalize_binance_trade(mock_msg)
                self._publish_event(MarketTickReceived, mock_msg)
                for cb in self._trade_subs[symbol]:
                    cb(trade)

            # Mock depth updates
            for symbol in list(self._depth_subs.keys()):
                sym_price = prices.get(symbol, 95000.0 if "BTC" in symbol else 3000.0)
                mock_msg = {
                    "e": "depthUpdate",
                    "E": int(time.time() * 1000),
                    "u": random.randint(100000, 999999),
                    "s": symbol,
                    "b": [[str(sym_price - 1.0), "0.5"]],
                    "a": [[str(sym_price + 1.0), "0.5"]],
                }
                depth = MarketDataNormalizer.normalize_binance_order_book(mock_msg, symbol=symbol)
                for cb in self._depth_subs[symbol]:
                    cb(depth)

            # Trigger random mock balance updates
            if random.random() < 0.05:
                asset = random.choice(["BTC", "ETH", "USDT"])
                self._publish_event(BalanceUpdated, {"asset": asset, "free": self._mock_balances[asset]})

            await asyncio.sleep(0.5)

    def _adjust_mock_balances(self, symbol: str, side: str, qty: float, price: float) -> None:
        """Simulate Spot balance changes when orders fill in Mock mode."""
        base = symbol.replace("USDT", "")
        cost = qty * price
        
        if side.upper() == "BUY":
            self._mock_balances["USDT"] = max(self._mock_balances["USDT"] - cost, 0.0)
            self._mock_balances[base] = self._mock_balances.get(base, 0.0) + qty
        else:
            self._mock_balances[base] = max(self._mock_balances.get(base, 0.0) - qty, 0.0)
            self._mock_balances["USDT"] = self._mock_balances["USDT"] + cost
        
        self._publish_event(AccountUpdated, {})
        self._publish_event(BalanceUpdated, {"asset": "USDT", "free": self._mock_balances["USDT"]})
        self._publish_event(BalanceUpdated, {"asset": base, "free": self._mock_balances[base]})
        self._publish_event(PositionUpdated, {"symbol": symbol, "amount": self._mock_balances[base]})

    def _publish_order_event(self, order_dict: dict) -> None:
        """Route order completions to trade journals/event bus."""
        self._publish_event(TradeExecuted, order_dict)

    # ── Health and Statistics API ──────────────────────────────────────

    def get_reconnect_history(self) -> list[str]:
        return list(self._reconnect_history)

    def health(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "reconnect_count": self._reconnect_count,
            "reconnect_history": list(self._reconnect_history),
            "latency_ms": self._latency_ms,
            "ws_connected": self._ws_connection is not None,
            "user_ws_connected": self._user_ws_connection is not None,
            "use_mock": self.use_mock,
        }
