# TOJI Binance Connectivity Report

This report documents the verification evidence for the consolidated Binance adapter endpoints.

---

## 1. Connection Configurations & Endpoint Proof
Both the public WebSocket gateway (`BinanceMarketGateway`) and the private trade client (`BinanceExchangeProvider`) consume the consolidated `BinanceEndpointConfig` model. On startup, the configuration details are printed exactly as verified:

```
======== TOJI BINANCE CONFIG ========

Market Provider:
binance_live

REST:
https://api.binance.com/api

WS:
wss://stream.binance.com:9443/ws

Trading:
PAPER

Real Orders:
DISABLED

====================================
```

### Verification of Suffix Correction (REST /api/v3/time):
Inside the application container (`toji-app`), the connection check verified that the REST client hits the correct endpoint prefix (`/api/v3/time`), returning a `200 OK` response:
```
2026-07-08 09:34:08,364 [INFO] httpx: HTTP Request: GET https://api.binance.com/api/v3/time "HTTP/1.1 200 OK"
2026-07-08 09:34:08,366 [INFO] toji.binance_provider: BinanceExchangeProvider: clock sync offset calculated: -83 ms
```
*Note: A search of the logs confirms that `api.binance.com/v3/time` does NOT exist in any connection request, and all routing goes strictly to `api.binance.com/api/v3/time`.*

---

## 2. Real-time Market Data Stream Ticks (binance_live)

Running a live stream validation captures the following real public ticks on the `binance_live` WS feed:

### First BTC Tick:
```json
{
  "symbol": "BTCUSDT",
  "price": 62180.01,
  "timestamp": "2026-07-08T09:34:52.267000+00:00",
  "volume": 0.00182
}
```

### First ETH Tick:
```json
{
  "symbol": "ETHUSDT",
  "price": 1740.0,
  "timestamp": "2026-07-08T09:34:52.508000+00:00",
  "volume": 0.0653
}
```

---

## 3. WebSocket Status
- **Target URL**: `wss://stream.binance.com:9443/ws`
- **SSL Fallback**: Active (gracefully retries without SSL verification if the execution environment lacks macOS certificate bindings).
- **Status**: `CONNECTED`
- **Mock status**: `FALSE` (synthetic stream inactive).

---

## 4. Test Suite Execution Proof
All tests in `tests/e2e/test_market_wiring.py` passed successfully:
```
======================== 11 passed, 1 warning in 3.38s =========================
```
Including:
- `test_binance_live_time_endpoint_correct`: PASSED (validated final request points to `/api/v3/time`)
- `test_no_duplicate_binance_url_builder`: PASSED (validated both gateway and exchange use the single `BinanceEndpointConfig` class)
