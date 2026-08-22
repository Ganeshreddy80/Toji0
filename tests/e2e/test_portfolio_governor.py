"""Regression tests: Portfolio Governor — Phase 12.

Scenarios covered:
  1. First BUY BTC  → APPROVED
  2. Second BUY BTC immediately (duplicate)  → BLOCKED (DUPLICATE_POSITION)
  3. Trade inside cooldown window  → BLOCKED (COOLDOWN_ACTIVE)
  4. Exposure / max-positions exceeded  → BLOCKED (MAX_POSITIONS)
  5. Valid different asset after BTC open  → APPROVED
  6. Rejected signals NEVER reach TradeManager (mock assert)
  7. Existing paper execution tests still import cleanly
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
import pytest

from research_platform.portfolio_governor.governor import PortfolioGovernor
from research_platform.portfolio_governor.models import GovernorConfig, PortfolioDecision
from research_platform.portfolio_governor.position_manager import PositionManager
from research_platform.portfolio_governor.exposure_manager import ExposureManager
from research_platform.portfolio_governor.cooldown_engine import CooldownEngine


# ── Helpers ───────────────────────────────────────────────────────────────────


def _signal(symbol: str, direction: str, signal_id: str = None) -> MagicMock:
    sig = MagicMock()
    sig.symbol = symbol
    sig.direction = direction
    sig.signal_id = signal_id or f"sig_{uuid.uuid4().hex[:6]}"
    return sig


def _make_governor(
    max_positions: int = 5,
    cooldown_seconds: float = 300.0,
    max_exposure: float = 0.80,
) -> PortfolioGovernor:
    config = GovernorConfig(
        max_open_positions=max_positions,
        max_portfolio_exposure_pct=max_exposure,
        default_cooldown_seconds=cooldown_seconds,
    )
    return PortfolioGovernor(config=config, event_bus=None)


# ── Scenario 1: First BUY approved ───────────────────────────────────────────


class TestScenario1_FirstBuyApproved:
    def test_first_buy_btc_is_approved(self):
        gov = _make_governor(cooldown_seconds=0)  # no cooldown for this test
        decision = gov.evaluate(_signal("BTCUSDT", "BUY"))
        assert decision.approved is True
        assert decision.reason == "APPROVED"


# ── Scenario 2: Duplicate position blocked ────────────────────────────────────


class TestScenario2_DuplicatePositionBlocked:
    def test_second_buy_btc_blocked(self):
        gov = _make_governor(cooldown_seconds=0)

        # First trade approved and fill recorded
        sig1 = _signal("BTCUSDT", "BUY")
        d1 = gov.evaluate(sig1)
        assert d1.approved is True
        gov.record_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        # Second BUY on same symbol — duplicate
        sig2 = _signal("BTCUSDT", "BUY")
        d2 = gov.evaluate(sig2)
        assert d2.approved is False
        assert d2.reason == "DUPLICATE_POSITION"

    def test_sell_to_close_long_is_allowed(self):
        """SELL on an existing LONG should be allowed (closing trade)."""
        gov = _make_governor(cooldown_seconds=0)

        gov.evaluate(_signal("BTCUSDT", "BUY"))
        gov.record_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        # SELL to close — should pass through
        d = gov.evaluate(_signal("BTCUSDT", "SELL"))
        assert d.approved is True


# ── Scenario 3: Cooldown blocks repeated trades ───────────────────────────────


class TestScenario3_CooldownBlocked:
    def test_trade_within_cooldown_window_is_blocked(self):
        gov = _make_governor(cooldown_seconds=300.0)

        sig1 = _signal("ETHUSDT", "BUY")
        d1 = gov.evaluate(sig1)
        assert d1.approved is True
        gov.record_fill("ETHUSDT", "BUY", 1.0, 3000.0)

        # Close the position so duplicate check doesn't fire
        gov._position_mgr.reduce_position("ETHUSDT", 1.0, 3000.0)

        # Immediately re-evaluate — cooldown should block
        sig2 = _signal("ETHUSDT", "BUY")
        d2 = gov.evaluate(sig2)
        assert d2.approved is False
        assert d2.reason == "COOLDOWN_ACTIVE"

    def test_trade_after_cooldown_expires_is_approved(self, monkeypatch):
        """After cooldown window passes, the same symbol is tradeable again."""
        gov = _make_governor(cooldown_seconds=10.0)

        gov.record_fill("SOLUSDT", "BUY", 1.0, 100.0)
        gov._position_mgr.reduce_position("SOLUSDT", 1.0, 100.0)

        # Fake the last trade time to be 11 seconds ago
        past = datetime.now(timezone.utc) - timedelta(seconds=11)
        gov._cooldown_engine._last_trade_time["SOLUSDT"] = past

        d = gov.evaluate(_signal("SOLUSDT", "BUY"))
        assert d.approved is True


# ── Scenario 4: Max positions (exposure) blocked ──────────────────────────────


class TestScenario4_MaxPositionsBlocked:
    def test_max_positions_exceeded_is_blocked(self):
        """With max_open_positions=2, a 3rd unique symbol should be blocked."""
        gov = _make_governor(max_positions=2, cooldown_seconds=0)

        # Fill 2 positions
        gov.evaluate(_signal("BTCUSDT", "BUY"))
        gov.record_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        gov.evaluate(_signal("ETHUSDT", "BUY"))
        gov.record_fill("ETHUSDT", "BUY", 1.0, 3000.0)

        # 3rd position should be blocked
        d = gov.evaluate(_signal("BNBUSDT", "BUY"))
        assert d.approved is False
        assert d.reason in ("MAX_POSITIONS", "EXPOSURE_LIMIT")

    def test_exposure_limit_triggered(self):
        """When exposure_pct check fires, reason is EXPOSURE_LIMIT."""
        # max_positions=3 so MAX_POSITIONS won't fire at 3rd position,
        # but exposure 3/3 = 100% > 80% threshold
        gov = _make_governor(max_positions=3, max_exposure=0.80, cooldown_seconds=0)

        gov.evaluate(_signal("BTCUSDT", "BUY"))
        gov.record_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        gov.evaluate(_signal("ETHUSDT", "BUY"))
        gov.record_fill("ETHUSDT", "BUY", 1.0, 3000.0)

        # 3rd position: 3/3 = 100% > 80% exposure
        d = gov.evaluate(_signal("BNBUSDT", "BUY"))
        assert d.approved is False
        assert d.reason == "EXPOSURE_LIMIT"


# ── Scenario 5: Valid different asset approved ────────────────────────────────


class TestScenario5_DifferentAssetApproved:
    def test_different_symbol_approved_while_btc_open(self):
        gov = _make_governor(max_positions=5, cooldown_seconds=0)

        gov.evaluate(_signal("BTCUSDT", "BUY"))
        gov.record_fill("BTCUSDT", "BUY", 1.0, 50000.0)

        d = gov.evaluate(_signal("ETHUSDT", "BUY"))
        assert d.approved is True
        assert d.reason == "APPROVED"


# ── Scenario 6: Rejected signals never reach TradeManager ────────────────────


class TestScenario6_RejectedNeverReachTradeManager:
    def test_blocked_signal_does_not_call_trade_manager(self):
        from research_platform.live_trading.orchestrator import LiveTradingOrchestrator

        event_bus = MagicMock()
        oms = MagicMock()
        ems = MagicMock()

        gov = _make_governor(cooldown_seconds=0)
        orchestrator = LiveTradingOrchestrator(
            event_bus=event_bus,
            oms=oms,
            ems=ems,
            governor=gov,
        )

        # Patch trade_manager so we can assert it's not called
        orchestrator._trade_manager = MagicMock()
        orchestrator._processor = MagicMock()
        orchestrator._processor.process_signal.return_value = True

        # First signal — fills and governor records position
        from research_platform.live_trading.models import ActiveSignal, OpenPosition
        from research_platform.live_trading.models import RecoveryCheckpoint
        sig1 = ActiveSignal(signal_id="s1", symbol="BTCUSDT", direction="BUY", strength=0.9)

        # Governor approves first — trade_manager is called
        orchestrator._trade_manager.execute_signal_trade.return_value = True
        orchestrator._account = MagicMock()
        orchestrator._recovery = MagicMock()
        orchestrator._repo = MagicMock()
        orchestrator._positions = MagicMock()
        _fake_open_pos = OpenPosition(
            symbol="BTCUSDT",
            quantity=1.0,
            entry_price=50000.0,
            current_price=50000.0,
            unrealized_pnl=0.0,
        )
        orchestrator._positions.update_position.return_value = _fake_open_pos
        orchestrator._session_manager = MagicMock()
        orchestrator._session_manager.session_id = "s1"

        result1 = orchestrator.ingest_market_signal(sig1)
        assert result1 is True
        orchestrator._trade_manager.execute_signal_trade.assert_called_once()
        orchestrator._trade_manager.reset_mock()

        # Second identical signal — governor must block before TradeManager
        sig2 = ActiveSignal(signal_id="s2", symbol="BTCUSDT", direction="BUY", strength=0.9)
        result2 = orchestrator.ingest_market_signal(sig2)
        assert result2 is False
        orchestrator._trade_manager.execute_signal_trade.assert_not_called()


# ── Scenario 7: Existing paper execution tests still importable ───────────────


class TestScenario7_PaperExecutionBackcompat:
    def test_paper_execution_imports_cleanly(self):
        """Ensure Phase 12 changes don't break Phase 11 paper execution module."""
        from research_platform.live_trading.trade_manager import TradeManager
        from research_platform.paper_market.paper_execution_router import PaperExecutionRouter
        from research_platform.paper_trading.plugin import PaperTradingPlugin
        assert TradeManager is not None
        assert PaperExecutionRouter is not None
        assert PaperTradingPlugin is not None

    def test_governor_portfolio_summary_structure(self):
        """get_portfolio_summary() must return all required keys."""
        gov = _make_governor()
        summary = gov.get_portfolio_summary()
        assert "open_positions" in summary
        assert "exposure" in summary
        assert "unrealized_pnl" in summary
        assert "realized_pnl" in summary
        assert "blocked_trades" in summary
        blocked = summary["blocked_trades"]
        assert "cooldown" in blocked
        assert "duplicate" in blocked
        assert "exposure" in blocked


# ── PositionManager unit tests ────────────────────────────────────────────────


class TestPositionManager:
    def test_open_and_get_position(self):
        pm = PositionManager()
        pos = pm.open_position("BTCUSDT", "LONG", 1.0, 50000.0)
        assert pos.symbol == "BTCUSDT"
        assert pos.side == "LONG"
        assert pos.quantity == 1.0

        retrieved = pm.get_position("BTCUSDT")
        assert retrieved is not None
        assert retrieved.symbol == "BTCUSDT"

    def test_reduce_position_to_zero_removes_it(self):
        pm = PositionManager()
        pm.open_position("ETHUSDT", "LONG", 2.0, 3000.0)
        pm.reduce_position("ETHUSDT", 2.0, 3100.0)
        assert pm.get_position("ETHUSDT") is None
        assert pm.open_count() == 0

    def test_weighted_average_entry_on_add(self):
        pm = PositionManager()
        pm.open_position("BTCUSDT", "LONG", 1.0, 40000.0)
        pm.open_position("BTCUSDT", "LONG", 1.0, 60000.0)
        pos = pm.get_position("BTCUSDT")
        assert pos.quantity == 2.0
        assert pos.average_entry_price == 50000.0


# ── CooldownEngine unit tests ─────────────────────────────────────────────────


class TestCooldownEngine:
    def test_no_cooldown_initially(self):
        config = GovernorConfig(default_cooldown_seconds=60.0)
        engine = CooldownEngine(config)
        ok, reason = engine.check("BTCUSDT")
        assert ok is True

    def test_cooldown_active_immediately_after_trade(self):
        config = GovernorConfig(default_cooldown_seconds=300.0)
        engine = CooldownEngine(config)
        engine.record_trade("BTCUSDT")
        ok, reason = engine.check("BTCUSDT")
        assert ok is False
        assert reason == "COOLDOWN_ACTIVE"

    def test_per_symbol_cooldown_override(self):
        config = GovernorConfig(
            default_cooldown_seconds=300.0,
            symbol_cooldowns={"BTCUSDT": 0.001},
        )
        engine = CooldownEngine(config)
        engine.record_trade("BTCUSDT")
        import time; time.sleep(0.002)
        ok, _ = engine.check("BTCUSDT")
        assert ok is True
