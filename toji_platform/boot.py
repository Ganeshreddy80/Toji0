"""Boot sequence for the Toji kernel.

Run from the command line::

    python -m toji_platform.boot
"""

from __future__ import annotations

import sys
import time
import logging
from datetime import datetime, timezone

from toji_platform.kernel import TojiKernel

# Subsystem Plugins
from market_gateway.core.gateway import MarketGateway
from universe.core.manager import UniverseManager
from market_intelligence.core.plugin import MarketIntelligencePlugin
from price_action.core.plugin import PriceActionPlugin
from confluence.core.plugin import ConfluencePlugin
from strategy.core.plugin import StrategyPlugin
from trading_context.core.plugin import TradingContextPlugin
from risk_engine.core.plugin import RiskEnginePlugin
from position_sizing.core.plugin import PositionSizingPlugin
from execution_engine.core.plugin import ExecutionEnginePlugin
from portfolio_engine.core.plugin import PortfolioPlatformPlugin
from dashboard.core.plugin import DashboardPlatformPlugin

import os
from dotenv import load_dotenv
from toji_platform.config_validator import validate_binance_env

logger = logging.getLogger("toji.boot")


def boot_kernel(
    config_overrides: dict[str, object] | None = None,
) -> TojiKernel:
    """Instantiate and boot the Toji kernel, loading all 12 subsystem plugins."""
    is_testing = "pytest" in sys.modules

    overrides = dict(config_overrides or {})
    if not is_testing:
        load_dotenv()
        validate_binance_env()
        if os.getenv("DEFAULT_EXCHANGE") == "binance":
            overrides.setdefault("execution.broker", "binance")
            if os.getenv("TRADING_MODE") == "paper":
                overrides.setdefault("market_gateway.provider_mode", "live")

    kernel = TojiKernel(config_overrides=overrides)

    # Determine provider mode
    mode = kernel.config.get("market_gateway.provider_mode")
    if not mode:
        mode = kernel.config.get("market.gateway.provider.mode", "replay")

    logger.info("Starting TOJI Platform Boot Coordinator. Mode: %s", mode)

    # 1. Instantiate MarketGateway and UniverseManager
    gateway = MarketGateway(event_bus=kernel.event_bus)
    kernel.container.register(MarketGateway, instance=gateway)

    if mode in ("live", "mock"):
        from market_gateway.providers.binance.client import BinanceGatewayProvider
        from market_gateway.providers.binance.exchange import BinanceExchangeProvider
        from universe.providers.binance import BinanceDiscoveryProvider

        use_mock = (mode == "mock")
        binance_provider = BinanceGatewayProvider(use_mock=use_mock)
        gateway.register_provider(binance_provider)
        kernel.container.register(BinanceExchangeProvider, instance=binance_provider)

        universe_manager = UniverseManager(event_bus=kernel.event_bus)
        binance_discovery = BinanceDiscoveryProvider(gateway_provider=binance_provider)
        universe_manager.discovery_engine.register_provider(binance_discovery)
    else:
        universe_manager = UniverseManager(event_bus=kernel.event_bus)

    # 2. Load all 12 plugins into PluginManager
    kernel.plugin_manager.load(gateway)
    kernel.plugin_manager.load(universe_manager)
    kernel.plugin_manager.load(MarketIntelligencePlugin(container=kernel.container))
    kernel.plugin_manager.load(PriceActionPlugin(container=kernel.container))
    kernel.plugin_manager.load(ConfluencePlugin(container=kernel.container))
    kernel.plugin_manager.load(StrategyPlugin(container=kernel.container))
    kernel.plugin_manager.load(TradingContextPlugin(container=kernel.container))
    kernel.plugin_manager.load(RiskEnginePlugin(container=kernel.container))
    kernel.plugin_manager.load(PositionSizingPlugin(container=kernel.container))
    kernel.plugin_manager.load(ExecutionEnginePlugin(container=kernel.container))
    kernel.plugin_manager.load(PortfolioPlatformPlugin(container=kernel.container))
    kernel.plugin_manager.load(DashboardPlatformPlugin(container=kernel.container))

    # 3. Perform Kernel Boot (initializes plugins in topological order, then runs lifecycle services)
    kernel.boot()

    # 4. If live/mock mode, trigger initial scan and set up streaming subscriptions
    if mode in ("live", "mock"):
        try:
            logger.info("Executing initial universe scan to discover and rank assets...")
            snapshot = universe_manager.run_scan()
            
            # Subscribe to all discovered/ranked symbols on the gateway
            for asset in snapshot.assets:
                # Use canonical symbol format (slash is handled by MarketGateway conversion layer)
                gateway.subscribe_candles(asset.symbol, "1m")
                gateway.subscribe_trades(asset.symbol)
            logger.info("Subscriptions successfully set up for all ranked symbols.")
        except Exception as e:
            logger.error("Failed to run initial scan or setup subscriptions: %s", e)

    return kernel


def main() -> None:
    """CLI entry point — boot, block for execution, then gracefully shut down on Ctrl+C."""
    print("=" * 60)
    print("  TOJI KERNEL — Boot Sequence")
    print("=" * 60)

    try:
        kernel = boot_kernel()
    except Exception as e:
        print(f"\n  Platform boot failed ✗: {e}")
        sys.exit(1)

    print(f"\n  Profile : {kernel.config.profile.value}")
    print(f"  Booted  : {kernel.is_booted}")

    health = kernel.health_check()
    if health:
        print("\n  Health checks:")
        for name, status in health.items():
            print(f"    {name}: {status.value}")
    else:
        print("\n  No health checks registered (kernel-only boot)")

    # Registries summary
    registries = {
        "Research Modules": kernel.research_registry.count(),
        "Agents": kernel.agent_registry.count(),
        "Playbooks": kernel.playbook_registry.count(),
        "Plugins": kernel.plugin_registry.count(),
        "Strategies": kernel.strategy_registry.count(),
        "Assets": kernel.asset_registry.count(),
        "Memory Providers": kernel.memory_provider_registry.count(),
        "Analytics Providers": kernel.analytics_provider_registry.count(),
    }
    print("\n  Registries:")
    for name, count in registries.items():
        print(f"    {name}: {count} registered")

    print(f"\n  Container services: {kernel.container.has('lifecycle_manager')}")
    print(f"  Event bus ready  : {isinstance(kernel.event_bus, object)}")

    print("\n" + "=" * 60)
    print("  TOJI PLATFORM IS RUNNING.")
    print("  Press Ctrl+C to initiate graceful shutdown.")
    print("=" * 60 + "\n")

    try:
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n\n  KeyboardInterrupt received. Initiating graceful shutdown...")
    finally:
        kernel.shutdown()

    print("\n  Kernel shut down successfully ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()

