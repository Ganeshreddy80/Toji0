"""Unit and integration tests for the TOJI Institutional Trade Journal.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator
from research_platform.trade_journal.models import TradeJournal

# Subsystem dependencies
from research_platform.oms.oms_core import OmsCore
from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
from research_platform.paper_market.orchestrator import PaperMarketOrchestrator
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.operations_center.operations_orchestrator import OperationsOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    trading_orch = PaperTradingOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator", instance=trading_orch)

    market_orch = PaperMarketOrchestrator(event_bus, container=c)
    c.register("research_platform.paper_market.orchestrator.PaperMarketOrchestrator", instance=market_orch)

    oms_orch = OmsCore(event_bus, container=c)
    c.register("research_platform.oms.oms_core.OmsCore", instance=oms_orch)

    ops_orch = OperationsOrchestrator(event_bus, container=c)
    c.register("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator", instance=ops_orch)

    return c


@pytest.fixture
def journal_orch(event_bus, container):
    return TradeJournalOrchestrator(event_bus, container=container)


def test_trade_journal_compilation_workflow(journal_orch, container, event_bus):
    """Verify that order fill triggers complete trade journal record, metrics, and downstreams."""
    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    oms_orch = container.resolve("research_platform.oms.oms_core.OmsCore")
    
    # Subscribes to events
    journal_orch.start_journaling()

    # Place a BUY order which will execute immediately to FILLED status
    order = oms_orch.submit_order(
        strategy_id="strat-alpha",
        symbol="AAPL",
        quantity=10,
        price=0.0,
        order_type="MARKET",
        side="BUY",
        rationale="Journal compilation test"
    )

    assert order.status == "FILLED"

    # Verify journal compiles in repository
    journals = journal_orch.repository.list_journals()
    assert len(journals) == 1
    
    journal = journals[0]
    assert isinstance(journal, TradeJournal)
    assert journal.symbol == "AAPL"
    assert journal.commission > 0.0
    assert journal.holding_time_sec >= 0.0
    assert journal.mfe > 0.0
    assert journal.mae > 0.0

    # Check stats calculated
    stats = journal_orch.repository.get_latest_statistics()
    assert stats is not None
    assert stats.win_rate == 1.0  # Profitable mock exit price
    assert stats.profit_factor > 0.0

    # Check daily journal aggregates
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily = journal_orch.repository.get_daily_journal(date_str)
    assert daily is not None
    assert daily.snapshot.total_trades_count == 1

    journal_orch.stop_journaling()


# ─────────────────────────────────────────────────────────────────────────────
# FP-4 Trade Journal Tests — ADR-001 / OQ-1 Compliance
# ─────────────────────────────────────────────────────────────────────────────


class MockPriceActionOrchTJ:
    def __init__(self, atr_val: float = 125.50):
        self._atr_val = atr_val
        self.calls = []

    def get_atr(self, symbol: str) -> float:
        self.calls.append(symbol)
        return self._atr_val


class MockFeaturePlatformOrchTJ:
    def __init__(self):
        self.queried_feature_lists = []

    def query_realtime(self, feature_names, symbols):
        self.queried_feature_lists.append(list(feature_names))
        import pandas as pd
        return pd.DataFrame([{"rsi": 55.0, "trend": "bullish", "support": 100.0, "resistance": 200.0, "close": 150.0}])


class MockTradeMemoryEngineTJ:
    def __init__(self):
        self.saved_trades = []

    def save_trade(self, **kwargs):
        self.saved_trades.append(kwargs)


def test_fp4_trade_journal_obtains_atr_from_pa(event_bus, container):
    """AC-4: TradeJournal obtains ATR from pa_orch.get_atr(symbol) and saves into trade memory."""
    mock_pa = MockPriceActionOrchTJ(atr_val=125.50)
    mock_fp = MockFeaturePlatformOrchTJ()
    mock_tm = MockTradeMemoryEngineTJ()

    container.register("PriceActionOrchestrator", instance=mock_pa)
    container.register("FeaturePlatformOrchestrator", instance=mock_fp)
    container.register("TradeMemoryEngine", instance=mock_tm)

    journal_orch = TradeJournalOrchestrator(event_bus, container=container)

    paper_orch = container.resolve("research_platform.paper_trading.orchestrator.PaperTradingOrchestrator")
    paper_orch.start_paper_session("acc-prod", 100000.0)

    oms_orch = container.resolve("research_platform.oms.oms_core.OmsCore")
    order = oms_orch.submit_order(
        strategy_id="strat-alpha",
        symbol="BTC/USDT",
        quantity=1,
        price=10000.0,
        order_type="MARKET",
        side="BUY",
        rationale="FP-4 ATR Test"
    )

    journal_orch.record_completed_trade(order.order_id)

    # 1. PA.get_atr was called
    assert "BTC/USDT" in mock_pa.calls, "AC-4 FAIL: TradeJournal must call pa_orch.get_atr()"

    # 2. Trade memory received canonical PA ATR
    assert len(mock_tm.saved_trades) == 1
    features_at_entry = mock_tm.saved_trades[0]["features_at_entry"]
    assert features_at_entry["ATR"] == 125.50, "AC-4 FAIL: features_at_entry['ATR'] must match PA ATR"
    assert features_at_entry["atr"] == 125.50, "AC-4 FAIL: features_at_entry['atr'] must match PA ATR"

    # 3. 'atr' was NOT in query_realtime feature names
    all_queried = [f for lst in mock_fp.queried_feature_lists for f in lst]
    assert "atr" not in all_queried, (
        f"AC-4 FAIL: TradeJournal must not query FP for 'atr'. Queried: {mock_fp.queried_feature_lists}"
    )
