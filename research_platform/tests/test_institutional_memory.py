"""Unit tests for the TOJI Institutional Memory Platform.
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timedelta, timezone

from toji_platform.core.event_bus import InMemoryEventBus
from research_platform.institutional_memory.models import Relationship
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.institutional_memory.trade_memory import TradeMemoryAdapter
from research_platform.institutional_memory.strategy_memory import StrategyMemoryAdapter
from research_platform.institutional_memory.risk_memory import RiskMemoryAdapter


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def orchestrator(event_bus):
    return InstitutionalMemoryOrchestrator(event_bus)


def test_append_only_versioned_memories(orchestrator):
    """Verify memory records are saved with version markers."""
    t_rec = TradeMemoryAdapter.create_record(
        trade_id="tr-1",
        symbol="BTCUSD",
        quantity=2.5,
        entry_price=45000.0,
        exit_price=46000.0,
        slippage_ms=12.0,
        quality="GOOD"
    )

    orchestrator.publish_memory("trades", t_rec)
    records = orchestrator.repository.list_memories_by_category("trades")
    
    assert len(records) == 1
    assert records[0].trade_id == "tr-1"
    assert records[0].metadata.version == 1


def test_relationships_traceability(orchestrator):
    """Verify parent and child lineage relationship tracking."""
    parent_id = "mem-strat-99"
    child_id = "mem-tr-1"

    rel = orchestrator.link_memories(parent_id, child_id, link_type="lineage")
    assert rel.parent_id == parent_id
    assert rel.child_id == child_id

    all_links = orchestrator.repository.list_relationships()
    assert len(all_links) == 1
    assert all_links[0].link_type == "lineage"


def test_deterministic_context_replay(orchestrator):
    """Verify reconstruction of state variables at target historical timestamps."""
    ts_now = datetime.now(timezone.utc)
    ts_past = ts_now - timedelta(seconds=10)


    # 1. Past record
    t_past = TradeMemoryAdapter.create_record(
        trade_id="t-old", symbol="ETHUSD", quantity=1.0,
        entry_price=3000.0, exit_price=3100.0, slippage_ms=5.0, quality="EXCELLENT"
    )
    # Mock past timestamp
    t_past = t_past.model_copy(update={
        "metadata": t_past.metadata.model_copy(update={"created_at": ts_past})
    })

    # 2. Present record
    t_now = TradeMemoryAdapter.create_record(
        trade_id="t-new", symbol="BTCUSD", quantity=1.0,
        entry_price=50000.0, exit_price=51000.0, slippage_ms=10.0, quality="GOOD"
    )

    orchestrator.publish_memory("trades", t_past)
    orchestrator.publish_memory("trades", t_now)

    # Reconstruct state at past timestamp
    snap = orchestrator.reconstruct_historical_state(ts_past + timedelta(seconds=1))
    
    # Snapshot should contain past trade only
    trade_ids = [t.trade_id for t in snap.trades]
    assert "t-old" in trade_ids
    assert "t-new" not in trade_ids


def test_structured_and_semantic_queries(orchestrator):
    """Verify search filter queries match targeted records."""
    # Create BTC trade
    t_btc = TradeMemoryAdapter.create_record(
        trade_id="tr-btc", symbol="BTCUSD", quantity=1.0,
        entry_price=45000.0, exit_price=46000.0, slippage_ms=12.0, quality="GOOD"
    )
    
    # Create Strategy with Sharpe improvement and ATR > 14
    s_atr = StrategyMemoryAdapter.create_record(
        strategy_id="strat-atr", version_tag="v1.1", sharpe=2.4, sortino=2.5, drawdown=0.08,
        params={"ATR": 15}, parent_ids=[]
    )

    orchestrator.publish_memory("trades", t_btc)
    orchestrator.publish_memory("strategies", s_atr)

    # Query 1: BTC trade
    res_btc = orchestrator.execute_search("Show BTC trades", filters={"symbol": "BTC", "high_volatility": False})
    assert len(res_btc) == 1
    assert res_btc[0].trade_id == "tr-btc"

    # Query 2: Sharpe improvement
    res_sharpe = orchestrator.execute_search("Find Sharpe", filters={"sharpe": 2.0})
    assert len(res_sharpe) == 1
    assert res_sharpe[0].strategy_id == "strat-atr"

    # Query 3: ATR > 14
    res_atr = orchestrator.execute_search("ATR greater than 14", filters={"atr_threshold": 14})
    assert len(res_atr) == 1
    assert res_atr[0].strategy_id == "strat-atr"


def test_lessons_extraction(orchestrator):
    """Verify lesson learned observations compiler logs validation state."""
    lesson = orchestrator.learn_from_trade(
        trade_id="tr-8",
        observation="Large bid-ask spread on Binance US",
        hypothesis="High spread increases entry slippage price",
        evidence="22.5ms latency resulted in 0.5% price difference",
        confidence=0.85,
        recommended_action="Route orders to Coinbase adapter when spread > 20bps"
    )

    assert lesson.validation_status == "PENDING_RESEARCH"
    assert lesson.trade_id == "tr-8"

    lessons = orchestrator.repository.list_memories_by_category("lessons")
    assert len(lessons) == 1
    assert lessons[0].lesson_id == lesson.lesson_id
