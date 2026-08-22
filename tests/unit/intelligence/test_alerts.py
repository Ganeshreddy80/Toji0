"""Unit tests for the Alert Manager."""

from __future__ import annotations

import pytest
import threading
from intelligence.models import AlertLevel
from intelligence.alerts.manager import AlertManager


@pytest.fixture
def manager() -> AlertManager:
    """Provide a fresh AlertManager instance."""
    return AlertManager()


def test_trigger_and_get_alerts(manager: AlertManager) -> None:
    """Test triggering multiple levels and retrieving them."""
    alert1 = manager.trigger_alert("BTC/USDT", AlertLevel.CRITICAL, "Crash", "Dump imminent")
    alert2 = manager.trigger_alert("ETH/USDT", AlertLevel.LOW, "Volume Peak", "Standard surge")

    assert alert1.alert_id.startswith("alert-")
    assert alert1.symbol == "BTC/USDT"
    assert alert1.level == AlertLevel.CRITICAL

    all_alerts = manager.get_alerts()
    assert len(all_alerts) == 2


def test_alert_filtering(manager: AlertManager) -> None:
    """Test alert list filtering by symbol and minimum severity levels."""
    manager.trigger_alert("BTC/USDT", AlertLevel.LOW, "L", "Low msg")
    manager.trigger_alert("BTC/USDT", AlertLevel.HIGH, "H", "High msg")
    manager.trigger_alert("ETH/USDT", AlertLevel.CRITICAL, "C", "Crit msg")

    # Filter by symbol
    btc_alerts = manager.get_alerts(symbol="BTC/USDT")
    assert len(btc_alerts) == 2

    # Filter by min level (HIGH or above)
    high_above = manager.get_alerts(min_level=AlertLevel.HIGH)
    assert len(high_above) == 2
    assert AlertLevel.LOW not in [a.level for a in high_above]

    # Filter by symbol and level combined
    btc_high = manager.get_alerts(min_level=AlertLevel.HIGH, symbol="BTC/USDT")
    assert len(btc_high) == 1
    assert btc_high[0].level == AlertLevel.HIGH


def test_clear_alerts(manager: AlertManager) -> None:
    """Test clear method resets recorded logs."""
    manager.trigger_alert("BTC/USDT", AlertLevel.LOW, "L", "Low msg")
    assert len(manager.get_alerts()) == 1

    manager.clear_alerts()
    assert len(manager.get_alerts()) == 0


def test_thread_safety(manager: AlertManager) -> None:
    """Verify thread-safe registration by concurrent triggers."""
    threads = []
    num_threads = 50

    def trigger_task() -> None:
        manager.trigger_alert("BTC/USDT", AlertLevel.MEDIUM, "T", "Thread task")

    for _ in range(num_threads):
        t = threading.Thread(target=trigger_task)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    assert len(manager.get_alerts()) == num_threads
