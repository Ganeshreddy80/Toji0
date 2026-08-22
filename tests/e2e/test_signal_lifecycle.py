import os
import sys
import pytest
import math
import uuid
from datetime import datetime, timezone, timedelta
import pandas as pd

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry
from data.schemas.market_data import OHLCV
from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
from research_platform.feature_platform.models import FeatureRecord
from research_platform.price_action.orchestrator import PriceActionOrchestrator
from research_platform.strategy_framework.composer import StrategyComposer
from research_platform.ai_signal.signal_generator import AISignalGenerator
from research_platform.risk_governance.ai_auditor import AIDecisionAuditor
from research_platform.risk_governance.kill_switch import KillSwitchEngine
from research_platform.risk_governance.risk_monitor import RealTimeRiskMonitor
from research_platform.oms.oms_core import OmsCore
from research_platform.execution_engine.simulator import ExchangeExecutionSimulator

def test_1000_candles_lifecycle():
    # 1. Force DEV mode to run locally in-memory
    os.environ["DATABASE_MODE"] = "DEV"
    os.environ["TOJI_MODE"] = "DEV"
    os.environ["TOJI_VALIDATION_MODE"] = "true"  # Enable validation mode for loose thresholds

    # Bootstrap the platform
    bootstrap_platform()
    container = ServiceRegistry().get_service("Container")

    # Clear previous dependencies if any
    pa_orch = container.resolve(PriceActionOrchestrator)
    fp_orch = container.resolve(FeaturePlatformOrchestrator)
    strategy_composer = container.resolve(StrategyComposer)
    ai_generator = container.resolve(AISignalGenerator)
    oms_core = container.resolve(OmsCore)

    from research_platform.paper_trading.orchestrator import PaperTradingOrchestrator
    paper_trading = container.resolve(PaperTradingOrchestrator)
    try:
        paper_trading.start_paper_session("test_session_lifecycle", 100000.0)
    except Exception:
        pass

    # Clean trackers
    pa_orch._bars.clear()
    pa_orch._tick_history.clear()

    # Define features to compute
    features_to_compute = [
        "open", "high", "low", "close", "ema9", "ema21", "ema50",
        "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
    ]
    feature_dependencies = {
        "open": [], "high": [], "low": [], "close": [], "volume": [],
        "ema9": ["close"], "ema21": ["close"], "ema50": ["close"],
        "rsi": ["close"], "atr": ["high", "low", "close"], "volume_change": ["volume"],
        "support": ["low"], "resistance": ["high"], "breakout": ["close", "resistance", "support"],
        "trend": ["ema9", "ema21"]
    }
    for name in features_to_compute:
        record = FeatureRecord(
            uuid=str(uuid.uuid4()), name=name, display_name=name.upper(), description="", formula=name,
            dependencies=feature_dependencies[name], category="Indicator", subcategory="Raw",
            owner="quants", author="CTO", version="1.0.0", update_frequency="1m",
            warmup_length=0, lookback_window=0, required_resolution="1m"
        )
        try:
            fp_orch.register_feature(record)
        except ValueError:
            pass

    symbol = "BTCUSDT"
    base_price = 50000.0
    tick_time = datetime.now(timezone.utc) - timedelta(minutes=1000)

    # Stats tracking
    stats = {
        "ticks": 0,
        "strategy_hold": 0,
        "strategy_buy_sell": 0,
        "ai_signals": 0,
        "ai_approved": 0,
        "executions": 0
    }

    # Generate 1000 candles using a wave pattern to trigger RSI and EMA crossings
    for i in range(1000):
        # Sine wave price movement: ranges between 48500 and 51500
        wave = math.sin(i / 10.0) * 1500.0
        price = base_price + wave
        volume = 100.0 + math.sin(i / 5.0) * 50.0
        tick_time += timedelta(minutes=1)

        candle = OHLCV(
            symbol=symbol,
            timestamp=tick_time,
            open=price - 10.0,
            high=price + 20.0,
            low=price - 20.0,
            close=price,
            volume=volume,
            interval="1m"
        )

        # 1. Price action update
        pa_orch.process_tick(symbol, price, candle.timestamp, volume)
        stats["ticks"] += 1

        # 2. Features calculation
        bars_list = pa_orch.get_bars(symbol)
        if len(bars_list) > 1:
            df = pd.DataFrame(bars_list)
        else:
            df = pd.DataFrame([candle.model_dump()])
        output_df = fp_orch.compute_and_store(features_to_compute, symbol, df)
        clean_features = output_df.iloc[-1].to_dict()

        # 3. Strategy composer
        strategy = strategy_composer.compose(
            strategy_id=f"strat_{symbol}",
            name="Mean Reversion E2E",
            strategy_type="MEAN_REVERSION",
            version="1.0.0",
            symbols=[symbol],
            parameters={"deviation": 1.5}
        )
        indicators = clean_features.copy()
        indicators["vwap"] = pa_orch.get_vwap(symbol)
        indicators["atr"] = pa_orch.get_atr(symbol)

        strategy_decision = strategy_composer.generate_decision(
            strategy=strategy,
            symbol=symbol,
            current_price=price,
            indicators=indicators
        )

        from strategy.core.enums import StrategyDecision
        decision_str = strategy_decision.value if isinstance(strategy_decision, StrategyDecision) else str(strategy_decision)
        if decision_str not in ("BUY", "SELL"):
            decision_str = "HOLD"

        if decision_str == "HOLD":
            stats["strategy_hold"] += 1
            continue

        stats["strategy_buy_sell"] += 1

        # 4. AI Signal Confluence
        ai_signal = ai_generator.generate_signal(symbol, price)
        if ai_signal.signal not in ("BUY", "SELL"):
            continue

        stats["ai_signals"] += 1

        # 5. AI Decision Auditor
        auditor = AIDecisionAuditor(min_confidence=0.55, min_risk_reward=1.0)  # Lower risk/reward check for validation
        signal_dict = {
            "signal": ai_signal.signal,
            "confidence": ai_signal.confidence,
            "reasoning": ai_signal.reasoning,
            "entry": price,
            "stop_loss": price - 100.0 if ai_signal.signal == "BUY" else price + 100.0,
            "take_profit": price + 150.0 if ai_signal.signal == "BUY" else price - 150.0
        }
        audit_decision = auditor.audit(signal_dict, regime="TRENDING")
        if not audit_decision.approved:
            continue

        stats["ai_approved"] += 1

        # 6. Risk Monitor
        risk_monitor = RealTimeRiskMonitor()
        risk_snap = risk_monitor.calculate_risk_score(
            capital=100000.0, open_positions=[], peak_capital=100000.0, leverage=1.0, consecutive_losses=0, daily_pnl=0.0
        )
        if risk_snap.risk_score < 40.0:
            continue

        # 7. OMS
        order = oms_core.submit_order(
            strategy_id=strategy.metadata.strategy_id,
            symbol=symbol,
            quantity=0.1,
            price=price,
            order_type="MARKET",
            side=ai_signal.signal,
            rationale=ai_signal.reasoning
        )
        if order.status not in ("VALIDATED", "QUEUED", "ROUTED", "FILLED"):
            continue

        # 8. Execution
        exec_sim = ExchangeExecutionSimulator(
            spread_bps=6.0, maker_fee=0.0002, taker_fee=0.0005, max_volume_pct=0.90
        )
        exec_result = exec_sim.simulate_order(
            symbol=symbol, side=ai_signal.signal, quantity=0.1, mid_price=price,
            market_volume=volume, atr=indicators.get("atr", 300.0), expected_entry=price, order_id=order.order_id
        )
        if exec_result["fill"].status == "FILLED":
            stats["executions"] += 1

    print("\nE2E Signal Lifecycle Stats:")
    print(stats)

    # Assertions
    assert stats["ticks"] == 1000
    assert stats["strategy_hold"] > 0
    assert stats["strategy_buy_sell"] > 0
    assert stats["ai_signals"] > 0, "No AI signals were generated during the 1000 candles run!"
    assert stats["ai_approved"] > 0
    assert stats["executions"] > 0
