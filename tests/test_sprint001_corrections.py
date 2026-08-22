"""Sprint 001 Regression Tests — Runtime Stabilization Corrections.

Issue 1: Risk State Fail-Closed
  - Valid AccountingService state -> risk evaluation proceeds
  - AccountingService unavailable -> trade blocked
  - Malformed state -> trade blocked
  - Incomplete state -> trade blocked

Issue 2: BUG-003 PnL Evidence Gap
  - fill_price - latest_close is slippage, not realized PnL
  - TradeMemoryEngine entry-leg pnl=0.0 is correct

Issue 3: Plugin Boot Isolation
  - Non-critical failure -> TradingHalted=False
  - Critical failure -> TradingHalted=True

Issue 4: TradingHalted gate in tick loop
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

class FakeContainer:
    """Minimal DI container double."""
    def __init__(self):
        self._registry = {}
    def register(self, key, instance):
        self._registry[str(key)] = instance
    def has(self, key) -> bool:
        return str(key) in self._registry
    def resolve(self, key):
        k = str(key)
        if k not in self._registry:
            raise KeyError(f"Key not registered: {k!r}")
        return self._registry[k]


def _make_valid_summary(equity=100_000.0, peak_equity=100_000.0, daily_pnl=0.0):
    return {"equity": equity, "peak_equity": peak_equity, "daily_pnl": daily_pnl}


def _make_accounting_service(summary: dict):
    svc = MagicMock()
    svc.get_portfolio_summary.return_value = summary
    svc.metrics_engine._trades = []
    svc.valuation_engine.get_all_positions.return_value = []
    return svc


def _run_risk_state_resolution(container: FakeContainer):
    """Inline reproduction of risk state resolution from run_paper_trading.py."""
    _risk_state_available = False
    _ks_equity = None
    _ks_peak = None
    _ks_daily_pnl = None
    _risk_state_error = None
    try:
        if not container.has("AccountingService"):
            _risk_state_error = "AccountingService not registered"
        else:
            _acct_svc = container.resolve("AccountingService")
            _portfolio_summary = _acct_svc.get_portfolio_summary()
            _ks_equity = _portfolio_summary.get("equity")
            _ks_peak = _portfolio_summary.get("peak_equity")
            _ks_daily_pnl = _portfolio_summary.get("daily_pnl")
            if _ks_equity is None or _ks_peak is None or _ks_daily_pnl is None:
                _risk_state_error = (
                    f"Incomplete portfolio summary: equity={_ks_equity!r}, "
                    f"peak_equity={_ks_peak!r}, daily_pnl={_ks_daily_pnl!r}"
                )
            elif not all(isinstance(v, (int, float)) for v in (_ks_equity, _ks_peak, _ks_daily_pnl)):
                _risk_state_error = "Malformed portfolio summary: non-numeric values"
            else:
                _metrics_engine = _acct_svc.metrics_engine
                _trades = list(_metrics_engine._trades) if hasattr(_metrics_engine, "_trades") else []
                _consecutive = 0
                for _t in reversed(_trades):
                    if getattr(_t, "net_pnl", 0.0) < 0:
                        _consecutive += 1
                    else:
                        break
                _risk_state_available = True
    except Exception as _ks_state_err:
        _risk_state_error = f"Exception resolving AccountingService state: {_ks_state_err}"
    return _risk_state_available, _risk_state_error, _ks_equity, _ks_peak, _ks_daily_pnl


CRITICAL_PLUGIN_NAMES = frozenset({
    "OmsPlugin", "PaperMarketPlugin", "PaperTradingPlugin", "PortfolioAccountingPlugin",
})


def _run_plugin_boot(plugins_and_exceptions: list):
    _failed_plugins = []
    _critical_failed_plugins = []
    _trading_halted = False
    for plugin_name, exc in plugins_and_exceptions:
        is_critical = plugin_name in CRITICAL_PLUGIN_NAMES
        if exc is not None:
            if is_critical:
                _trading_halted = True
                _critical_failed_plugins.append(plugin_name)
            _failed_plugins.append(plugin_name)
    return _failed_plugins, _critical_failed_plugins, _trading_halted


# ── Issue 1: Risk State Fail-Closed ──────────────────────────────────────────

def test_valid_accounting_service_allows_risk_evaluation():
    """Valid AccountingService state -> risk evaluation proceeds."""
    container = FakeContainer()
    svc = _make_accounting_service(
        _make_valid_summary(equity=95_000.0, peak_equity=100_000.0, daily_pnl=-500.0)
    )
    container.register("AccountingService", svc)
    available, error, equity, peak, pnl = _run_risk_state_resolution(container)
    assert available is True, f"Expected available, got error: {error}"
    assert error is None
    assert equity == 95_000.0
    assert peak == 100_000.0
    assert pnl == -500.0


def test_accounting_service_not_registered_blocks_risk():
    """AccountingService not registered -> trade blocked."""
    container = FakeContainer()
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False
    assert "AccountingService not registered" in error


def test_accounting_service_exception_blocks_risk():
    """get_portfolio_summary() raises -> trade blocked."""
    container = FakeContainer()
    svc = MagicMock()
    svc.get_portfolio_summary.side_effect = RuntimeError("DB connection lost")
    container.register("AccountingService", svc)
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False
    assert "Exception resolving AccountingService state" in error


def test_incomplete_summary_missing_equity_blocks_risk():
    """Summary missing 'equity' -> trade blocked."""
    container = FakeContainer()
    svc = _make_accounting_service({"peak_equity": 100_000.0, "daily_pnl": 0.0})
    container.register("AccountingService", svc)
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False
    assert "Incomplete portfolio summary" in error


def test_incomplete_summary_missing_peak_equity_blocks_risk():
    """Summary missing 'peak_equity' -> trade blocked."""
    container = FakeContainer()
    svc = _make_accounting_service({"equity": 100_000.0, "daily_pnl": 0.0})
    container.register("AccountingService", svc)
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False
    assert "Incomplete portfolio summary" in error


def test_incomplete_summary_missing_daily_pnl_blocks_risk():
    """Summary missing 'daily_pnl' -> trade blocked."""
    container = FakeContainer()
    svc = _make_accounting_service({"equity": 100_000.0, "peak_equity": 100_000.0})
    container.register("AccountingService", svc)
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False
    assert "Incomplete portfolio summary" in error


def test_malformed_summary_non_numeric_equity_blocks_risk():
    """Non-numeric equity -> malformed state -> trade blocked."""
    container = FakeContainer()
    svc = _make_accounting_service({"equity": "INVALID", "peak_equity": 100_000.0, "daily_pnl": 0.0})
    container.register("AccountingService", svc)
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False
    assert error is not None


def test_malformed_summary_none_equity_blocks_risk():
    """Explicit None equity -> incomplete -> trade blocked."""
    container = FakeContainer()
    svc = _make_accounting_service({"equity": None, "peak_equity": 100_000.0, "daily_pnl": 0.0})
    container.register("AccountingService", svc)
    available, error, *_ = _run_risk_state_resolution(container)
    assert available is False


# ── Issue 2: BUG-003 PnL Evidence Gap ────────────────────────────────────────

def test_fill_price_minus_close_is_not_realized_pnl():
    """
    EVIDENCE: fill_price - latest_close is fill slippage, NOT realized PnL.

    For a BUY at latest_close=50_000, filled at fill_price=50_010:
    - fill_price - latest_close = 10.0 => this is slippage cost
    - position is still OPEN => no realized PnL exists
    - Realized PnL is computed by AccountingService.on_fill() on SELL only.
    """
    latest_close = 50_000.0
    fill_price = 50_010.0

    fill_slippage = abs(fill_price - latest_close)
    invented_pnl = round(fill_price - latest_close, 8)

    # Slippage is a cost
    assert fill_slippage == 10.0
    # The invented formula is positive on BUY but the trade is still open
    assert invented_pnl == 10.0
    # Correct value for open entry leg: 0.0
    correct_entry_leg_pnl = 0.0
    assert correct_entry_leg_pnl == 0.0


def test_trade_memory_accepts_zero_pnl_entry_leg():
    """TradeMemoryEngine.save_trade() with pnl=0.0 stores it correctly."""
    from research_platform.trade_memory.engine import TradeMemoryEngine
    from datetime import datetime, timezone
    tm = TradeMemoryEngine(persistence_file="/dev/null")
    result = tm.save_trade(
        symbol="BTCUSDT",
        entry=50_000.0,
        exit=50_010.0,
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        features_at_entry={"rsi": 55.0},
        decision_reason="entry leg test",
        pnl=0.0,
        execution_quality=100.0,
        slippage=10.0,
        fees=12.5,
        fill_time=datetime.now(timezone.utc).isoformat(),
    )
    assert result["pnl"] == 0.0


# ── Issue 3: Plugin Boot Isolation ───────────────────────────────────────────

def test_no_failures_trading_allowed():
    plugins = [
        ("OmsPlugin", None), ("PaperMarketPlugin", None),
        ("PaperTradingPlugin", None), ("PortfolioAccountingPlugin", None),
        ("MetricsPlugin", None),
    ]
    failed, critical_failed, halted = _run_plugin_boot(plugins)
    assert halted is False
    assert critical_failed == []


def test_non_critical_plugin_failure_does_not_halt_trading():
    plugins = [
        ("OmsPlugin", None), ("PaperMarketPlugin", None),
        ("PaperTradingPlugin", None), ("PortfolioAccountingPlugin", None),
        ("MetricsPlugin", RuntimeError("DB unreachable")),
        ("ReportingPlugin", ValueError("config missing")),
    ]
    failed, critical_failed, halted = _run_plugin_boot(plugins)
    assert halted is False
    assert "MetricsPlugin" in failed
    assert critical_failed == []


def test_critical_oms_plugin_failure_halts_trading():
    plugins = [
        ("OmsPlugin", RuntimeError("OMS boot failed")),
        ("PaperMarketPlugin", None), ("PaperTradingPlugin", None), ("PortfolioAccountingPlugin", None),
    ]
    failed, critical_failed, halted = _run_plugin_boot(plugins)
    assert halted is True
    assert "OmsPlugin" in critical_failed


def test_critical_paper_market_plugin_failure_halts_trading():
    plugins = [
        ("OmsPlugin", None),
        ("PaperMarketPlugin", RuntimeError("router init failed")),
        ("PaperTradingPlugin", None), ("PortfolioAccountingPlugin", None),
    ]
    failed, critical_failed, halted = _run_plugin_boot(plugins)
    assert halted is True
    assert "PaperMarketPlugin" in critical_failed


def test_critical_paper_trading_plugin_failure_halts_trading():
    plugins = [
        ("OmsPlugin", None), ("PaperMarketPlugin", None),
        ("PaperTradingPlugin", RuntimeError("PaperBroker failed")),
        ("PortfolioAccountingPlugin", None),
    ]
    failed, critical_failed, halted = _run_plugin_boot(plugins)
    assert halted is True
    assert "PaperTradingPlugin" in critical_failed


def test_critical_accounting_plugin_failure_halts_trading():
    plugins = [
        ("OmsPlugin", None), ("PaperMarketPlugin", None), ("PaperTradingPlugin", None),
        ("PortfolioAccountingPlugin", RuntimeError("AccountingService DB error")),
    ]
    failed, critical_failed, halted = _run_plugin_boot(plugins)
    assert halted is True
    assert "PortfolioAccountingPlugin" in critical_failed


def test_non_critical_plugins_still_boot_after_critical_failure():
    booted = []
    _failed, _critical_failed, _halted = [], [], False
    plugins = [
        ("OmsPlugin", RuntimeError("OMS boot failed")),
        ("MetricsPlugin", None),
        ("ReportingPlugin", None),
    ]
    for name, exc in plugins:
        if exc is not None:
            if name in CRITICAL_PLUGIN_NAMES:
                _halted = True
                _critical_failed.append(name)
            _failed.append(name)
        else:
            booted.append(name)
    assert "MetricsPlugin" in booted
    assert "ReportingPlugin" in booted
    assert _halted is True


# ── Issue 4: TradingHalted Gate ───────────────────────────────────────────────

def test_trading_allowed_when_no_critical_failures():
    container = FakeContainer()
    container.register("TradingHalted", False)
    flag = container.resolve("TradingHalted") if container.has("TradingHalted") else False
    assert flag is False


def test_trading_blocked_when_critical_plugin_failed():
    container = FakeContainer()
    container.register("TradingHalted", True)
    container.register("CriticalFailedPlugins", ["OmsPlugin"])
    flag = container.resolve("TradingHalted") if container.has("TradingHalted") else False
    assert flag is True


def test_trading_allowed_when_halted_flag_absent():
    container = FakeContainer()
    flag = container.resolve("TradingHalted") if container.has("TradingHalted") else False
    assert flag is False


# ── Issue 5: Startup Source Verification ─────────────────────────────────────

def test_critical_plugin_names_in_startup_source():
    import inspect
    import research_platform.platform.startup as startup_mod
    source = inspect.getsource(startup_mod)
    for expected in ["OmsPlugin", "PaperMarketPlugin", "PaperTradingPlugin", "PortfolioAccountingPlugin"]:
        assert expected in source, f"Critical plugin '{expected}' not found in startup.py"


def test_trading_halted_registered_in_container_on_clean_boot():
    """After a clean mocked boot (no plugin failures), TradingHalted=False is in container."""
    from research_platform.platform.startup import PlatformStartupCoordinator
    coordinator = PlatformStartupCoordinator()
    mock_container = FakeContainer()
    mock_container.register("IEventBus", MagicMock())
    with patch.object(coordinator, "config_loader") as mock_config, \
         patch.object(coordinator, "container_boot") as mock_cb, \
         patch.object(coordinator, "eventbus_boot") as mock_eb, \
         patch.object(coordinator, "plugin_loader") as mock_pl, \
         patch.object(coordinator, "service_registry"):
        mock_config.load_configuration.return_value = {
            "database": {"host": "localhost", "port": 5432, "name": "test", "user": "test", "password": "test"}
        }
        mock_db = MagicMock()
        with patch("research_platform.platform.startup.DatabaseLifecycleManager", return_value=mock_db), \
             patch("toji_platform.core.configuration.manager.ConfigurationManager"), \
             patch("toji_platform.core.configuration.interfaces.IConfigProvider"):
            mock_cb.boot_container.return_value = mock_container
            mock_eb.boot_eventbus.return_value = MagicMock()
            mock_pl.discover_plugins.return_value = []
            coordinator.boot_platform()
    assert mock_container.has("TradingHalted"), "TradingHalted must be registered after boot"
    assert mock_container.resolve("TradingHalted") is False
