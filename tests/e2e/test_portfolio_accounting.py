"""Regression tests: Portfolio Accounting — Phase 13.

Scenarios:
  1. Position valuation updates after market tick
  2. Portfolio equity changes after BUY fill
  3. Unrealized PnL computed correctly (long, price up)
  4. Closing trade realizes PnL and removes unrealized
  5. Trade journal entry created with all required fields on close
  6. Metrics: win rate and total return after 2 closed trades
  7. MFE and MAE tracked correctly across multiple ticks
  8. Runtime API portfolio key exposes accounting values
  9. 1,000-tick performance: average update < 5ms per tick
  10. No duplicate position records after multiple ticks
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from research_platform.portfolio_accounting.accounting_service import AccountingService
from research_platform.portfolio_accounting.models import (
    PortfolioMetrics,
    PortfolioSnapshot,
    TradeRecord,
    ValuatedPosition,
)
from research_platform.portfolio_accounting.position_valuation_engine import PositionValuationEngine
from research_platform.portfolio_accounting.portfolio_accounting_engine import PortfolioAccountingEngine
from research_platform.portfolio_accounting.metrics_engine import MetricsEngine
from research_platform.portfolio_accounting.trade_journal import TradeJournal


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_bus() -> MagicMock:
    """Return a mock EventBus that silently accepts publish/subscribe."""
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.subscribe = MagicMock()
    return bus


def _make_service(balance: float = 100_000.0) -> AccountingService:
    return AccountingService(event_bus=_make_bus(), initial_balance=balance)


def _fill_event(symbol: str, side: str, quantity: float, price: float, **kwargs) -> MagicMock:
    ev = MagicMock()
    ev.payload = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        **kwargs,
    }
    return ev


def _tick_event(symbol: str, price: float) -> MagicMock:
    ev = MagicMock()
    ev.payload = {"symbol": symbol, "price": price}
    return ev


# ── Scenario 1: Valuation updates on market tick ──────────────────────────────


class TestScenario1_ValuationUpdatesOnTick:
    def test_tick_updates_current_price(self):
        svc = _make_service()

        # Open position
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        pos = svc.valuation_engine.get_position("BTCUSDT")
        assert pos is not None
        assert pos.current_price == 50000.0

        # Tick at higher price
        svc.on_market_tick(_tick_event("BTCUSDT", 51000.0))
        pos = svc.valuation_engine.get_position("BTCUSDT")
        assert pos.current_price == 51000.0

    def test_tick_updates_market_value(self):
        svc = _make_service()
        svc.on_fill(_fill_event("ETHUSDT", "BUY", 2.0, 3000.0))
        svc.on_market_tick(_tick_event("ETHUSDT", 3200.0))
        pos = svc.valuation_engine.get_position("ETHUSDT")
        assert pos.market_value == pytest.approx(6400.0)


# ── Scenario 2: Portfolio equity changes on BUY fill ─────────────────────────


class TestScenario2_EquityChangesOnBuyFill:
    def test_equity_decreases_after_buy(self):
        balance = 100_000.0
        svc = _make_service(balance)

        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        positions = svc.valuation_engine.get_all_positions()
        snapshot = svc._accounting_engine.recalculate(positions)

        # cash = 100000 - 50000*(1+commisson+slippage)
        # portfolio_value = cash + market_value_open_positions
        # equity must still roughly equal initial_balance (minus fees)
        assert 98_000.0 < snapshot.equity < 100_001.0, f"Unexpected equity: {snapshot.equity}"
        assert snapshot.open_position_count == 1

    def test_buying_power_does_not_exceed_cash(self):
        svc = _make_service(10_000.0)
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 0.1, 50000.0))
        positions = svc.valuation_engine.get_all_positions()
        snapshot = svc._accounting_engine.recalculate(positions)
        assert snapshot.buying_power >= 0.0
        assert snapshot.buying_power <= 10_000.0


# ── Scenario 3: Unrealized PnL computed correctly ────────────────────────────


class TestScenario3_UnrealizedPnl:
    def test_long_price_up_positive_unrealized(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_market_tick(_tick_event("BTCUSDT", 51000.0))

        pos = svc.valuation_engine.get_position("BTCUSDT")
        assert pos.unrealized_pnl == pytest.approx(1000.0)
        assert pos.pnl_percent > 0.0

    def test_long_price_down_negative_unrealized(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_market_tick(_tick_event("BTCUSDT", 49000.0))

        pos = svc.valuation_engine.get_position("BTCUSDT")
        assert pos.unrealized_pnl == pytest.approx(-1000.0)
        assert pos.pnl_percent < 0.0

    def test_portfolio_unrealized_matches_sum_of_positions(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_fill(_fill_event("ETHUSDT", "BUY", 2.0, 3000.0))
        svc.on_market_tick(_tick_event("BTCUSDT", 51000.0))
        svc.on_market_tick(_tick_event("ETHUSDT", 3100.0))

        positions = svc.valuation_engine.get_all_positions()
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        snapshot = svc._accounting_engine.recalculate(positions)
        assert snapshot.unrealized_pnl == pytest.approx(total_unrealized)


# ── Scenario 4: Closing trade realizes PnL ───────────────────────────────────


class TestScenario4_CloseRealizesPnl:
    def test_close_removes_position_and_realizes_pnl(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_market_tick(_tick_event("BTCUSDT", 51000.0))

        # Close at 51000
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 51000.0))

        # Position should be gone
        pos = svc.valuation_engine.get_position("BTCUSDT")
        assert pos is None

        # Snapshot reflects no open positions
        positions = svc.valuation_engine.get_all_positions()
        assert len(positions) == 0

    def test_realized_pnl_positive_after_profitable_close(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 52000.0))

        # realized_pnl should reflect the gain (~2000 minus fees)
        snapshot = svc._accounting_engine.recalculate([])
        assert snapshot.realized_pnl > 0.0, f"realized_pnl={snapshot.realized_pnl}"

    def test_realized_pnl_negative_on_losing_close(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 48000.0))
        snapshot = svc._accounting_engine.recalculate([])
        assert snapshot.realized_pnl < 0.0, f"realized_pnl={snapshot.realized_pnl}"


# ── Scenario 5: Trade journal entry with all required fields ──────────────────


class TestScenario5_TradeJournalEntry:
    def test_journal_entry_created_on_close(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0, strategy="momentum"))
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 51000.0, strategy="momentum"))

        entries = svc.trade_journal.get_all()
        assert len(entries) == 1

    def test_journal_entry_has_required_fields(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0,
                                strategy="momentum", ai_confidence=0.87))
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 51500.0,
                                strategy="momentum", ai_confidence=0.87))

        entry = svc.trade_journal.get_all()[0]
        assert entry.symbol == "BTCUSDT"
        assert entry.quantity == 1.0
        assert entry.entry_price == pytest.approx(50000.0)
        assert entry.exit_price == pytest.approx(51500.0)
        assert entry.realized_pnl > 0.0
        assert entry.net_pnl > 0.0
        assert entry.return_pct > 0.0
        assert entry.holding_duration_seconds >= 0.0
        assert entry.trade_id.startswith("trd-")

    def test_no_journal_on_open_only(self):
        svc = _make_service()
        svc.on_fill(_fill_event("ETHUSDT", "BUY", 2.0, 3000.0))
        assert len(svc.trade_journal.get_all()) == 0


# ── Scenario 6: Metrics after closed trades ───────────────────────────────────


class TestScenario6_Metrics:
    def _make_two_closed_trades(self, svc: AccountingService) -> None:
        """One winner, one loser."""
        svc.on_fill(_fill_event("BTCUSDT", "BUY",  1.0, 50000.0))
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 52000.0))  # winner +2000

        svc.on_fill(_fill_event("ETHUSDT", "BUY",  1.0, 3000.0))
        svc.on_fill(_fill_event("ETHUSDT", "SELL", 1.0, 2800.0))   # loser -200

    def test_win_rate_is_0_5_after_one_win_one_loss(self):
        svc = _make_service()
        self._make_two_closed_trades(svc)
        positions = svc.valuation_engine.get_all_positions()
        snapshot = svc._accounting_engine.recalculate(positions)
        metrics = svc._metrics_engine.compute(100_000.0, snapshot.equity, positions)

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == pytest.approx(0.5)

    def test_total_return_pct_updates(self):
        svc = _make_service(100_000.0)
        self._make_two_closed_trades(svc)
        positions = svc.valuation_engine.get_all_positions()
        snapshot = svc._accounting_engine.recalculate(positions)
        metrics = svc._metrics_engine.compute(100_000.0, snapshot.equity, positions)
        # Net gain ~ +1800 (2000 win - 200 loss - fees)
        assert metrics.total_return_pct != 0.0

    def test_profit_factor_computed(self):
        svc = _make_service()
        self._make_two_closed_trades(svc)
        positions = svc.valuation_engine.get_all_positions()
        snapshot = svc._accounting_engine.recalculate(positions)
        metrics = svc._metrics_engine.compute(100_000.0, snapshot.equity, positions)
        assert metrics.profit_factor >= 0.0


# ── Scenario 7: MFE and MAE ───────────────────────────────────────────────────


class TestScenario7_MFEandMAE:
    def test_mfe_tracks_highest_favorable_excursion(self):
        engine = PositionValuationEngine()
        engine.on_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        engine.on_tick("BTCUSDT", 51000.0)  # +1000 favorable
        engine.on_tick("BTCUSDT", 52000.0)  # +2000 favorable — MFE
        engine.on_tick("BTCUSDT", 50500.0)  # retraces

        pos = engine.get_position("BTCUSDT")
        assert pos.max_favorable_excursion == pytest.approx(2000.0)

    def test_mae_tracks_worst_adverse_excursion(self):
        engine = PositionValuationEngine()
        engine.on_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        engine.on_tick("BTCUSDT", 49000.0)  # -1000 adverse
        engine.on_tick("BTCUSDT", 48000.0)  # -2000 adverse — MAE
        engine.on_tick("BTCUSDT", 50200.0)  # recovers

        pos = engine.get_position("BTCUSDT")
        assert pos.max_adverse_excursion == pytest.approx(-2000.0)

    def test_highest_and_lowest_prices_tracked(self):
        engine = PositionValuationEngine()
        engine.on_fill("ETHUSDT", "BUY", 1.0, 3000.0)

        prices = [3100.0, 2900.0, 3300.0, 2850.0, 3050.0]
        for p in prices:
            engine.on_tick("ETHUSDT", p)

        pos = engine.get_position("ETHUSDT")
        assert pos.highest_price_seen == pytest.approx(3300.0)
        assert pos.lowest_price_seen  == pytest.approx(2850.0)


# ── Scenario 8: Runtime API portfolio key ────────────────────────────────────


class TestScenario8_RuntimeApiPortfolioKey:
    def test_get_portfolio_summary_returns_all_required_keys(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_market_tick(_tick_event("BTCUSDT", 51000.0))

        summary = svc.get_portfolio_summary()

        required_keys = {
            "cash_balance", "equity", "portfolio_value", "buying_power",
            "realized_pnl", "unrealized_pnl", "daily_pnl", "fees",
            "open_positions", "positions",
        }
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    def test_positions_list_has_position_data(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        summary = svc.get_portfolio_summary()

        assert len(summary["positions"]) == 1
        pos = summary["positions"][0]
        assert pos["symbol"] == "BTCUSDT"
        assert "unrealized_pnl" in pos
        assert "pnl_percent" in pos
        assert "mfe" in pos
        assert "mae" in pos

    def test_metrics_key_present_after_closed_trade(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY",  1.0, 50000.0))
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.0, 51000.0))
        summary = svc.get_portfolio_summary()
        assert "metrics" in summary
        assert "win_rate" in summary["metrics"]


# ── Scenario 9: Performance — 1,000 ticks ───────────────────────────────────


class TestScenario9_Performance:
    def test_1000_ticks_under_5ms_average(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        svc.on_fill(_fill_event("ETHUSDT", "BUY", 2.0, 3000.0))

        prices = [50000.0 + i * 10 for i in range(1000)]
        start = time.perf_counter()
        for p in prices:
            svc.on_market_tick(_tick_event("BTCUSDT", p))
        elapsed_ms = (time.perf_counter() - start) * 1000

        avg_ms = elapsed_ms / 1000
        assert avg_ms < 5.0, f"Average tick time too slow: {avg_ms:.3f}ms"

    def test_10000_ticks_total_under_50ms(self):
        """Direct valuation engine bench — bypasses event bus overhead."""
        engine = PositionValuationEngine()
        engine.on_fill("BTCUSDT", "BUY", 1.0, 50000.0)
        engine.on_fill("ETHUSDT", "BUY", 2.0, 3000.0)
        engine.on_fill("BNBUSDT", "BUY", 5.0, 300.0)

        start = time.perf_counter()
        for i in range(10_000):
            engine.on_tick("BTCUSDT", 50000.0 + i * 0.01)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50.0, f"10k ticks took {elapsed_ms:.1f}ms (target: <50ms)"


# ── Scenario 10: No duplicate position records ────────────────────────────────


class TestScenario10_NoDuplicatePositions:
    def test_multiple_ticks_single_position_record(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))

        for price in [50100.0, 50200.0, 50300.0, 50400.0]:
            svc.on_market_tick(_tick_event("BTCUSDT", price))

        positions = svc.valuation_engine.get_all_positions()
        btc_positions = [p for p in positions if p.symbol == "BTCUSDT"]
        assert len(btc_positions) == 1, f"Got {len(btc_positions)} BTCUSDT positions"

    def test_two_fills_same_symbol_merged_not_duplicated(self):
        svc = _make_service()
        svc.on_fill(_fill_event("ETHUSDT", "BUY", 1.0, 3000.0))
        svc.on_fill(_fill_event("ETHUSDT", "BUY", 1.0, 3100.0))  # add to position

        positions = svc.valuation_engine.get_all_positions()
        eth_positions = [p for p in positions if p.symbol == "ETHUSDT"]
        assert len(eth_positions) == 1
        assert eth_positions[0].quantity == pytest.approx(2.0)
        # Weighted average entry: (3000 + 3100) / 2 = 3050
        assert eth_positions[0].average_entry == pytest.approx(3050.0)


# ── Module import smoke test ──────────────────────────────────────────────────


class TestImportSmoke:
    def test_all_accounting_modules_import(self):
        from research_platform.portfolio_accounting import (
            AccountingService,
            PortfolioAccountingPlugin,
            ValuatedPosition,
            PortfolioSnapshot,
            TradeRecord,
            PortfolioMetrics,
        )
        assert AccountingService is not None

    def test_events_import(self):
        from research_platform.portfolio_accounting.events import (
            PortfolioUpdated,
            PositionValuationUpdated,
            TradeClosed,
            PortfolioMetricsUpdated,
        )
        assert PortfolioUpdated is not None

    def test_plugin_instantiable(self):
        from research_platform.portfolio_accounting.plugin import PortfolioAccountingPlugin
        container = MagicMock()
        container.has.return_value = False
        container.resolve.return_value = _make_bus()
        plugin = PortfolioAccountingPlugin(container)
        assert plugin is not None


class TestScenarioPhase16_DecoupledAccounting:
    def test_ledger_append_only_violations(self):
        from research_platform.portfolio_accounting.ledger_repository import LedgerRepository
        from research_platform.portfolio_accounting.models import TradeLedgerEntry
        from datetime import datetime, timezone

        repo = LedgerRepository()
        entry1 = TradeLedgerEntry(
            trade_id="trd_test_1",
            order_id="ord_test_1",
            symbol="BTCUSDT",
            side="BUY",
            quantity=1.0,
            entry_price=50000.0,
            exit_price=0.0,
            commission=25.0,
            slippage=5.0,
            realized_pnl=0.0,
            timestamp=datetime.now(timezone.utc)
        )
        repo.append(entry1)

        # Attempting to overwrite existing trade_id must raise ValueError
        with pytest.raises(ValueError, match="cannot overwrite existing trade_id"):
            repo.append(entry1)

    def test_performance_engine_sortino_ratio(self):
        from research_platform.portfolio_accounting.performance_engine import PerformanceEngine
        from research_platform.portfolio_accounting.models import TradeRecord
        from datetime import datetime, timezone

        engine = PerformanceEngine()
        # Record three equity ticks to simulate returns (100k -> 105k -> 102k)
        engine.record_equity(100000.0)
        engine.record_equity(105000.0)  # +5% return
        engine.record_equity(102000.0)  # -2.85% return

        metrics = engine.compute(100000.0, 102000.0, [])
        assert metrics.loss_rate == 0.0  # no trades yet
        assert metrics.sortino_ratio != 0.0  # Sortino calculated on downside returns
        assert len(metrics.equity_curve) == 3

    def test_scaling_partial_close_accounting(self):
        svc = _make_service()
        # 1. Open long position BTCUSDT 2.0 @ 50,000
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 2.0, 50000.0))
        pos1 = svc.valuation_engine.get_position("BTCUSDT")
        assert pos1.quantity == 2.0
        assert pos1.average_entry == 50000.0

        # 2. Scale into position (add 1.0 @ 52,000)
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 52000.0))
        pos2 = svc.valuation_engine.get_position("BTCUSDT")
        assert pos2.quantity == 3.0
        # Avg entry = (2*50k + 1*52k)/3 = 50666.67
        assert pos2.average_entry == pytest.approx(50666.6666)

        # 3. Scale out / Partial close (sell 1.5 @ 55,000)
        # Note: self._entry_times will pop BTCUSDT time when side is SELL, so we seed it again for subsequent close
        svc._entry_times["BTCUSDT"] = datetime.now(timezone.utc)
        svc.on_fill(_fill_event("BTCUSDT", "SELL", 1.5, 55000.0))
        pos3 = svc.valuation_engine.get_position("BTCUSDT")
        assert pos3.quantity == 1.5
        assert pos3.average_entry == pytest.approx(50666.6666)

        # 4. Verify realized PnL on partial close
        summary = svc.get_portfolio_summary()
        assert summary["realized_pnl"] > 0.0

    def test_status_api_mapped_keys(self):
        svc = _make_service()
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))
        summary = svc.get_portfolio_summary()

        # Check for Phase 16 specific keys
        assert "cash" in summary
        assert "commission" in summary
        assert "slippage" in summary
        assert "drawdown" in summary
        assert "peak_equity" in summary
        assert "daily_return" in summary
        assert "total_return" in summary
        assert "trade_count" in summary
        assert "win_rate" in summary
        assert "profit_factor" in summary
        assert summary["cash"] == pytest.approx(100000.0 - 50000.0 - 25.0 - 5.0)

    def test_events_publishing(self):
        bus = _make_bus()
        from research_platform.portfolio_accounting.accounting_service import AccountingService
        svc = AccountingService(event_bus=bus, initial_balance=100000.0)

        # Trigger fill
        svc.on_fill(_fill_event("BTCUSDT", "BUY", 1.0, 50000.0))

        # Inspect calls to publish on the event bus
        assert bus.publish.call_count >= 4
        calls = [call[0][0].__class__.__name__ for call in bus.publish.call_args_list]
        assert "PortfolioUpdated" in calls
        assert "PnLUpdated" in calls
        assert "DrawdownUpdated" in calls
        assert "PerformanceUpdated" in calls
