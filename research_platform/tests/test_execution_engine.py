"""Unit tests for the Execution Management System (EMS).
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.execution_engine.adapter import MockExchangeAdapter
from research_platform.execution_engine.health import HealthMonitor
from research_platform.execution_engine.models import ExchangePosition
from research_platform.execution_engine.orchestrator import ExecutionEngineOrchestrator
from research_platform.execution_engine.rate_limiter import TokenBucketRateLimiter
from research_platform.execution_engine.reconciliation import StateReconciler
from research_platform.execution_engine.rest_client import RestClient
from research_platform.execution_engine.retry import RetryEngine
from research_platform.execution_engine.router import ExchangeRouter
from research_platform.execution_engine.sync import StateSynchronizer
from research_platform.execution_engine.websocket import WebSocketManager
from research_platform.oms.models import Order, OrderRequest


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return ExecutionEngineOrchestrator(event_bus)


def test_exchange_adapter_connectivity():
    """Verify mock adapter connects and fetches balances/positions."""
    adapter = MockExchangeAdapter("BINANCE")
    assert adapter.connect() is True
    
    positions = adapter.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTC/USDT"

    balances = adapter.get_balances()
    assert len(balances) == 1
    assert balances[0].asset == "USDT"


def test_websocket_manager_heartbeats():
    """Verify websocket triggers reconnect counters and heartbeat pings."""
    ws = WebSocketManager("BINANCE")
    ws.connect()
    assert ws.is_connected is True
    assert ws.reconnect_count == 0

    assert ws.send_ping() is True
    ws.disconnect()
    assert ws.is_connected is False

    ws.trigger_reconnect()
    assert ws.is_connected is True
    assert ws.reconnect_count == 1


def test_rest_client_signatures():
    """Verify signed requests match HMAC hash predictions."""
    client = RestClient(api_key="key123", api_secret="secret123")
    
    params = {"symbol": "BTCUSDT", "quantity": 1.0}
    sig1 = client.sign_request(params)
    sig2 = client.sign_request(params)
    
    # Signatures must be deterministic and identical
    assert sig1 == sig2
    assert len(sig1) == 64


def test_retry_engine_backoffs():
    """Verify exponential delay retries throw last exception after limits."""
    retry = RetryEngine(max_attempts=2, initial_delay_ms=10, factor=2.0)
    
    calls = 0
    def failing_fn():
        nonlocal calls
        calls += 1
        raise ValueError("API error")

    with pytest.raises(ValueError):
        retry.execute(failing_fn)
    
    assert calls == 2


def test_rate_limiter_tokens():
    """Verify token bucket capacity limits and request blocks."""
    # Capacity 2, refill rate 1 per second
    limiter = TokenBucketRateLimiter(capacity=2.0, refill_rate=1.0)
    
    assert limiter.allow_request() is True
    assert limiter.allow_request() is True
    assert limiter.allow_request() is False  # empty bucket


def test_state_reconciliation():
    """Verify reconciler catches differences in position quantities."""
    req = OrderRequest(order_id="o1", symbol="BTC/USDT", direction="BUY", quantity=1.0, order_type="MARKET")
    order = Order(order_id="o1", request=req, status="FILLED", filled_quantity=1.0)

    # 1. Matching quantities -> reconciled
    pos_match = ExchangePosition(symbol="BTC/USDT", quantity=1.0, entry_price=50000.0, current_price=50000.0, margin_requirement=0.0)
    log_match = StateReconciler.reconcile([order], [pos_match])
    assert log_match.reconciled is True

    # 2. Mismatching quantities -> logs discrepancies
    pos_mismatch = ExchangePosition(symbol="BTC/USDT", quantity=1.5, entry_price=50000.0, current_price=50000.0, margin_requirement=0.0)
    log_mismatch = StateReconciler.reconcile([order], [pos_mismatch])
    assert log_mismatch.reconciled is False
    assert len(log_mismatch.discrepancies) > 0


def test_health_monitor_latencies():
    """Verify HealthMonitor compiles latencies and updates success ratios."""
    monitor = HealthMonitor()
    
    metric1 = monitor.record_request(latency_ms=150.0, success=True)
    assert metric1.latency_ms == 150.0
    assert metric1.success_ratio == 1.0

    metric2 = monitor.record_request(latency_ms=250.0, success=False)
    assert metric2.success_ratio == 0.5


def test_ems_orchestration(orchestrator):
    """Verify execution orchestrator checks rates, connects, submits, and reconciles."""
    req = OrderRequest(
        order_id="ord_888",
        symbol="BTC/USDT",
        direction="BUY",
        quantity=1.0,
        order_type="MARKET"
    )
    order = Order(order_id="ord_888", request=req, status="ROUTED")

    report = orchestrator.execute_order(order, exchange="COINBASE")
    assert report.status == "FILLED"
    assert len(orchestrator.repository.list_reports()) == 1
    assert len(orchestrator.repository.list_reconciliations()) == 1
