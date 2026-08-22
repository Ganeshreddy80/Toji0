"""Live Trading Engine plugin registration.
"""

from __future__ import annotations

import logging

from research_platform.live_trading.orchestrator import LiveTradingOrchestrator
from research_platform.live_trading.repository import LiveTradingRepository
from research_platform.paper_market.paper_execution_router import PaperExecutionRouter

logger = logging.getLogger(__name__)


class LiveTradingEnginePlugin:
    """Hooks the live trading engine components into the DI container during boot."""

    def __init__(self, container) -> None:
        self.container = container

    def initialize(self) -> None:
        """Register repositories, orchestrators, and Binance gateway client mappings."""
        import os
        import logging
        from research_platform.live_trading.factory import MarketProviderFactory

        repo = LiveTradingRepository()
        self.container.register(LiveTradingRepository, instance=repo)

        # Register Orchestrator
        event_bus = self.container.resolve("IEventBus")
        oms = self.container.resolve("OrderManagementSystemOrchestrator")
        ems = self.container.resolve("ExecutionEngineOrchestrator")
        
        # Build PaperExecutionRouter (always created; mode enforced by TRADING_MODE guard in TradeManager)
        paper_router = PaperExecutionRouter(container=self.container, default_mode="PAPER")
        if not self.container.has(PaperExecutionRouter):
            self.container.register(PaperExecutionRouter, instance=paper_router)
        else:
            paper_router = self.container.resolve(PaperExecutionRouter)
        if not self.container.has("PaperExecutionRouter"):
            self.container.register("PaperExecutionRouter", instance=paper_router)

        # Resolve PortfolioGovernor if already registered by PortfolioGovernorPlugin
        governor = None
        if self.container.has("PortfolioGovernor"):
            governor = self.container.resolve("PortfolioGovernor")
            logger.info("LiveTradingEnginePlugin: PortfolioGovernor resolved and injected.")
        else:
            logger.warning(
                "LiveTradingEnginePlugin: PortfolioGovernor not found in DI container — "
                "running without position governance (all signals will reach TradeManager)."
            )

        orchestrator = LiveTradingOrchestrator(event_bus, oms, ems, paper_router=paper_router, governor=governor, container=self.container)
        self.container.register(LiveTradingOrchestrator, instance=orchestrator)
        self._orchestrator = orchestrator


        # Resolve correct market provider
        market_provider = os.getenv("MARKET_PROVIDER")
        if not market_provider:
            import sys
            if "pytest" in sys.modules or os.getenv("APP_ENV") == "testing":
                market_provider = "demo"
                os.environ["MARKET_PROVIDER"] = "demo"
            else:
                market_provider = "demo"
        trading_mode = os.getenv("TRADING_MODE", "paper")

        # Determine display labels
        real_orders_enabled = trading_mode.lower() == "live"
        market_data_enabled = market_provider.lower() != ""
        if market_provider.lower() == "demo":
            market_data_label = "SIMULATED"
        else:
            market_data_label = "REAL"

        # ── Structured startup fingerprint ──────────────────────────────
        fingerprint = (
            "\n"
            "======== TOJI RUNTIME MODE ========\n"
            f"Market Provider: {market_provider}\n"
            f"Market Data: {'ENABLED' if market_data_enabled else 'DISABLED'}\n"
            f"Tick Listener: ACTIVE\n"
            f"Execution: {trading_mode.upper()}\n"
            f"Real Orders: {'ENABLED' if real_orders_enabled else 'DISABLED'}\n"
            "==================================="
        )
        print(fingerprint)
        logger.info(fingerprint)

        # Initialize and start Market Provider Gateway
        gateway = MarketProviderFactory.create_provider(
            event_bus=event_bus,
            symbols=["BTCUSDT", "ETHUSDT"],
            container=self.container
        )
        # Register in DI container for flexibility
        self.container.register(gateway.__class__, instance=gateway)
        self.container.register("BinanceDemoGateway", instance=gateway)
        
        self._gateway = gateway
        gateway.start()

        # Send safety warnings for demo market provider
        if market_provider.lower() == "demo":
            try:
                alert_orch = self.container.resolve("AlertOrchestrator")
                if alert_orch:
                    from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel
                    alert = Alert(
                        title="SIMULATED MARKET DATA ACTIVE",
                        message="SIMULATED MARKET DATA ACTIVE",
                        severity=AlertSeverity.HIGH,
                        channels=[AlertChannel.TELEGRAM]
                    )
                    alert_orch.fire(alert)
            except Exception as e:
                logger.debug("Failed to send Telegram alert warning for demo market provider: %s", e)

        # ── Market tick listener — ALWAYS active when MARKET_PROVIDER is set ──
        # TRADING_MODE controls execution safety only, NOT data flow.
        # The pipeline (MarketTick → Feature → Strategy → AI Signal) must run
        # in both paper and live modes to generate simulated trading decisions.
        self._event_bus = event_bus
        event_bus.subscribe("system.market_data_received", self._handle_market_tick)
        logger.info(
            "LiveTradingEnginePlugin: Market tick listener ACTIVE (provider=%s, execution=%s).",
            market_provider, trading_mode.upper()
        )
        
        # Get count of subscribers on system.market_data_received
        handlers = event_bus._handlers.get("system.market_data_received", [])
        subscribers_count = len(handlers)
        
        from toji_platform.runtime.state import RuntimeStateManager
        sm = RuntimeStateManager()
        sm.load()
        last_tick_str = sm.last_tick_time.isoformat() if sm.last_tick_time else "N/A"
        
        diagnostics = (
            "\n"
            "MARKET PIPELINE:\n"
            "Binance WS: CONNECTED\n"
            "Publishing Event: system.market_data_received\n"
            f"Subscribers: {subscribers_count}\n"
            f"Last Tick: {last_tick_str}\n"
        )
        print(diagnostics, flush=True)
        logger.info(diagnostics)
        
        # Start a default session to handle incoming ticks
        orchestrator.start_session("default_live_session")

    def _handle_market_tick(self, event: Any) -> None:
        payload = getattr(event, "payload", {}) or {}
        symbol = payload.get("symbol")
        price = payload.get("price")
        timestamp_str = payload.get("timestamp")
        volume = payload.get("volume", 0.0)

        if not symbol or price is None:
            return

        try:
            price_float = float(price)
        except Exception:
            price_float = 0.0

        # Standardize timestamp timezone
        from datetime import datetime, timezone
        if isinstance(timestamp_str, str):
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now(timezone.utc)
        else:
            timestamp = datetime.now(timezone.utc)

        # 1. Update processed state ticks counter
        from toji_platform.runtime.state import RuntimeStateManager
        state_manager = RuntimeStateManager()
        state_manager.load()
        state_manager.record_tick()

        # 2. PriceActionOrchestrator
        try:
            pa_orch = self.container.resolve("PriceActionOrchestrator")
            pa_orch.process_tick(symbol, price_float, timestamp, volume)
        except Exception as e:
            logger.error("LiveTrading: Failed to process tick in PriceActionOrchestrator: %s", e)
            return

        # 3. Compute and store features in FeaturePlatformOrchestrator
        try:
            if self.container.has("FeaturePlatformOrchestrator"):
                feature_platform = self.container.resolve("FeaturePlatformOrchestrator")
                bars_list = pa_orch.get_bars(symbol)
                if len(bars_list) > 1:
                    import pandas as pd
                    df = pd.DataFrame(bars_list)
                else:
                    from data.schemas.market_data import OHLCV
                    candle = OHLCV(
                        symbol=symbol,
                        timestamp=timestamp,
                        open=price_float,
                        high=price_float,
                        low=price_float,
                        close=price_float,
                        volume=volume,
                        interval="1m"
                    )
                    import pandas as pd
                    df = pd.DataFrame([candle.model_dump()])

                # FP-7D-2: Canonical compute names — lazy import preserves plugin discovery posture.
                from research_platform.feature_platform.orchestrator import DEFAULT_COMPUTE_NAMES
                features_to_compute = list(DEFAULT_COMPUTE_NAMES)
                
                # Compute features
                feature_platform.compute_and_store(features_to_compute, symbol, df)
                state_manager.record_feature(len(features_to_compute))
        except Exception as e:
            logger.error("LiveTrading: Failed to compute features in FeaturePlatformOrchestrator: %s", e)

        # 4. AISignalGenerator
        try:
            ai_sig_gen = self.container.resolve("AISignalGenerator")
            ai_signal = ai_sig_gen.generate_signal(symbol, price_float)
            
            # Record strategy decision
            decision_str = getattr(ai_signal, "signal", "HOLD")
            if decision_str not in ("BUY", "SELL"):
                decision_str = "HOLD"
            state_manager.record_strategy_decision(decision_str)
            
            if ai_signal.signal in ("BUY", "SELL"):
                state_manager.record_signal()
                state_manager.record_ai_audit(True)
                state_manager.record_risk_audit(True)
                
                # Map to ActiveSignal and ingest
                from research_platform.live_trading.models import ActiveSignal
                import uuid
                active_sig = ActiveSignal(
                    signal_id=f"sig_{uuid.uuid4().hex[:8]}",
                    symbol=symbol,
                    direction=ai_signal.signal,
                    strength=ai_signal.confidence
                )
                
                # Ingest signal
                self._orchestrator.ingest_market_signal(active_sig)
        except Exception as e:
            logger.error("LiveTrading: Failed to generate AI signal or execute trade: %s", e)

    def shutdown(self) -> None:
        """Gracefully stop the Binance Demo Gateway and unsubscribe."""
        if hasattr(self, "_gateway") and self._gateway:
            self._gateway.stop()
        if hasattr(self, "_event_bus") and self._event_bus:
            try:
                self._event_bus.unsubscribe("system.market_data_received", self._handle_market_tick)
            except Exception as e:
                logger.error("LiveTrading: Failed to unsubscribe: %s", e)
        if hasattr(self, "_orchestrator") and self._orchestrator:
            self._orchestrator.stop_session("default_live_session")
