"""Unit tests for Trade Journal service."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
from datetime import datetime, timezone, date
from dataclasses import dataclass
from pathlib import Path
import pytest

from toji_platform.core.event_bus import InMemoryEventBus
from toji_platform.core.event_bus.events import BaseEvent
from toji_platform.services.trade_journal import TradeJournal


@pytest.fixture
def temp_journal_dir():
    dir_path = tempfile.mkdtemp()
    yield dir_path
    shutil.rmtree(dir_path)


def test_trade_journal_recording_and_query(temp_journal_dir):
    journal = TradeJournal(base_dir=temp_journal_dir)
    journal.start()

    entry1 = {
        "timestamp": "2026-06-28T12:00:00Z",
        "symbol": "BTC/USDT",
        "side": "BUY",
        "quantity": 1.0,
        "price": 50000.0,
        "realized_pnl": 0.0,
    }
    entry2 = {
        "timestamp": "2026-06-28T13:00:00Z",
        "symbol": "ETH/USDT",
        "side": "SELL",
        "quantity": 10.0,
        "price": 3000.0,
        "realized_pnl": 150.0,
    }

    journal.record(entry1)
    journal.record(entry2)

    # Force flush
    journal.stop()

    # Query all
    results = journal.query(start_date=date(2026, 6, 28), end_date=date(2026, 6, 28))
    assert len(results) == 2
    assert results[0]["symbol"] == "BTC/USDT"
    assert results[1]["symbol"] == "ETH/USDT"

    # Query filtered by symbol
    eth_results = journal.query(start_date=date(2026, 6, 28), end_date=date(2026, 6, 28), symbol="ETH/USDT")
    assert len(eth_results) == 1
    assert eth_results[0]["symbol"] == "ETH/USDT"


def test_trade_journal_event_bus_integration(temp_journal_dir):
    bus = InMemoryEventBus()
    journal = TradeJournal(base_dir=temp_journal_dir, event_bus=bus)
    journal.start()

    # Create dummy execution completed event
    @dataclass(frozen=True)
    class ExecutionCompleted(BaseEvent):
        pass

    event = ExecutionCompleted(
        source="test_broker",
        payload={
            "execution_id": "exec-1",
            "symbol": "BTC/USDT",
            "side": "BUY",
            "quantity": 2.5,
            "price": 60000.0,
            "latency_ms": 15.2,
        }
    )

    bus.publish(event)
    journal.stop()  # flushes buffer

    results = journal.query(symbol="BTC/USDT")
    assert len(results) == 1
    assert results[0]["execution_id"] == "exec-1"
    assert results[0]["quantity"] == 2.5


def test_trade_journal_thread_safety(temp_journal_dir):
    journal = TradeJournal(base_dir=temp_journal_dir, flush_interval=0.1)
    journal.start()

    def worker(worker_id: int):
        for i in range(50):
            journal.record({
                "timestamp": "2026-06-28T12:00:00Z",
                "symbol": f"SYM-{worker_id}",
                "quantity": float(i),
            })

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    journal.stop()

    results = journal.query(start_date=date(2026, 6, 28), end_date=date(2026, 6, 28))
    assert len(results) == 250
