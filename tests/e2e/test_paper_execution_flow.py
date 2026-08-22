"""Regression test: TOJI Paper Execution Flow.

Verifies end-to-end order routing when TRADING_MODE=paper:
  Signal → TradeManager → PaperExecutionRouter → PaperTradingOrchestrator → FILLED

Guarantees:
- ExecutionEngineOrchestrator is NEVER called in paper mode.
- PaperExecutionRouter.route_order() IS called with correct arguments.
- Orders reach PaperTradingOrchestrator.submit_paper_order() and return FILLED.
- TradeManager returns True on success.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import MagicMock, patch, call


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_routed_order():
    """Return a minimal stub that satisfies OMS.ingest_order() return value."""
    order = MagicMock()
    order.order_id = "routed-123"
    return order


def _make_paper_order(status: str = "FILLED"):
    """Return a stub PaperOrder with the given status."""
    po = MagicMock()
    po.status = status
    return po


# ── TradeManager unit tests ───────────────────────────────────────────────────


class TestTradeManagerPaperRouting:
    """TradeManager must route to PaperExecutionRouter when TRADING_MODE=paper."""

    def _build_trade_manager(self, paper_router):
        from research_platform.live_trading.trade_manager import TradeManager
        oms = MagicMock()
        oms.ingest_order.return_value = _make_routed_order()
        ems = MagicMock()
        return TradeManager(oms=oms, ems=ems, paper_router=paper_router), oms, ems

    def test_paper_mode_calls_paper_router(self, monkeypatch):
        """EMS must NOT be called; PaperExecutionRouter must be called."""
        monkeypatch.setenv("TRADING_MODE", "paper")

        paper_router = MagicMock()
        paper_router.route_order.return_value = _make_paper_order("FILLED")

        mgr, oms, ems = self._build_trade_manager(paper_router)
        result = mgr.execute_signal_trade("oid-1", "BTCUSDT", "BUY", 0.01, 50000.0)

        assert result is True
        paper_router.route_order.assert_called_once_with(
            strategy_id="oid-1",
            symbol="BTCUSDT",
            quantity=0.01,
            price=50000.0,
            order_type="MARKET",
            side="BUY",
            rationale="signal_trade",
        )
        ems.execute_order.assert_not_called()

    def test_paper_mode_no_router_returns_false(self, monkeypatch):
        """If paper_router is None in paper mode, trade must be gracefully dropped."""
        monkeypatch.setenv("TRADING_MODE", "paper")

        mgr, oms, ems = self._build_trade_manager(paper_router=None)
        result = mgr.execute_signal_trade("oid-2", "ETHUSDT", "SELL", 0.1, 3000.0)

        assert result is False
        ems.execute_order.assert_not_called()

    def test_paper_mode_unfilled_order_returns_false(self, monkeypatch):
        """PARTIAL or REJECTED orders must return False."""
        monkeypatch.setenv("TRADING_MODE", "paper")

        paper_router = MagicMock()
        paper_router.route_order.return_value = _make_paper_order("PARTIAL")

        mgr, oms, ems = self._build_trade_manager(paper_router)
        result = mgr.execute_signal_trade("oid-3", "BTCUSDT", "BUY", 0.01, 50000.0)
        assert result is False

    def test_live_mode_calls_ems_not_paper_router(self, monkeypatch):
        """In LIVE mode EMS must be called and PaperExecutionRouter must NOT be called."""
        monkeypatch.setenv("TRADING_MODE", "live")

        paper_router = MagicMock()
        ems_report = MagicMock()
        ems_report.status = "FILLED"

        from research_platform.live_trading.trade_manager import TradeManager
        oms = MagicMock()
        oms.ingest_order.return_value = _make_routed_order()
        ems = MagicMock()
        ems.execute_order.return_value = ems_report

        mgr = TradeManager(oms=oms, ems=ems, paper_router=paper_router)
        result = mgr.execute_signal_trade("oid-4", "BTCUSDT", "BUY", 0.01, 50000.0)

        assert result is True
        ems.execute_order.assert_called_once()
        paper_router.route_order.assert_not_called()


# ── PaperExecutionRouter unit tests ──────────────────────────────────────────


class TestPaperExecutionRouter:
    """PaperExecutionRouter must resolve PaperTradingOrchestrator and call submit_paper_order."""

    def test_paper_mode_routes_to_paper_orchestrator(self):
        from research_platform.paper_market.paper_execution_router import PaperExecutionRouter

        paper_orch = MagicMock()
        paper_orch.submit_paper_order.return_value = _make_paper_order("FILLED")

        container = MagicMock()
        container.has.return_value = True
        container.resolve.return_value = paper_orch

        router = PaperExecutionRouter(container=container, default_mode="PAPER")
        result = router.route_order(
            strategy_id="strat-1",
            symbol="BTCUSDT",
            quantity=0.01,
            price=50000.0,
            order_type="LIMIT",
            side="BUY",
            rationale="regression"
        )

        paper_orch.submit_paper_order.assert_called_once_with(
            strategy_id="strat-1",
            symbol="BTCUSDT",
            quantity=0.01,
            price=50000.0,
            order_type="LIMIT",
            side="BUY",
            rationale="regression",
        )
        assert result.status == "FILLED"

    def test_paper_mode_raises_when_orchestrator_missing(self):
        from research_platform.paper_market.paper_execution_router import PaperExecutionRouter

        container = MagicMock()
        container.has.return_value = False

        router = PaperExecutionRouter(container=container, default_mode="PAPER")
        with pytest.raises(RuntimeError, match="PaperTradingOrchestrator registry not found"):
            router.route_order(
                strategy_id="strat-2",
                symbol="ETHUSDT",
                quantity=0.1,
                price=3000.0,
                order_type="LIMIT",
                side="SELL",
                rationale="regression"
            )


# ── PaperTradingPlugin boot test ──────────────────────────────────────────────


class TestPaperTradingPluginBoot:
    """Plugin must auto-start a default paper session on initialize()."""

    def test_auto_starts_default_paper_session(self):
        from research_platform.paper_trading.plugin import PaperTradingPlugin

        event_bus = MagicMock()

        container = MagicMock()
        container.resolve.return_value = event_bus
        container.has.return_value = False  # full-key not yet registered

        with patch(
            "research_platform.paper_trading.plugin.PaperTradingOrchestrator"
        ) as MockOrch:
            orch_instance = MagicMock()
            MockOrch.return_value = orch_instance

            plugin = PaperTradingPlugin(container=container)
            plugin.initialize()

            orch_instance.start_paper_session.assert_called_once_with(
                account_id="default_paper_account",
                initial_balance=100_000.0,
            )
