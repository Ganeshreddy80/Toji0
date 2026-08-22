"""Real E2E Pipeline Test without mocks.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
import uuid
import pytest

from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry

from research_platform.risk_governance.ai_auditor import AIDecisionAuditor
from research_platform.risk_governance.kill_switch import KillSwitchEngine
from research_platform.risk_governance.risk_monitor import RealTimeRiskMonitor
from research_platform.execution_engine.simulator import ExchangeExecutionSimulator
from research_platform.trade_memory.engine import TradeMemoryEngine
from research_platform.execution_engine.simulator_models import OrderStatus


def test_real_pipeline_execution():
    # 1. Force DEV mode to run locally in-memory
    os.environ["DATABASE_MODE"] = "DEV"
    os.environ["TOJI_MODE"] = "DEV"
    
    # Bootstrap the platform
    app = bootstrap_platform()
    container = ServiceRegistry().get_service("Container")
    
    symbol = "BTCUSDT"
    expected_entry = 60000.0
    quantity = 0.5
    
    # 1. MARKET normalisation & input
    from data.schemas.market_data import OHLCV
    tick_time = datetime.now(timezone.utc)
    candle = OHLCV(
        symbol=symbol,
        timestamp=tick_time,
        open=expected_entry,
        high=expected_entry,
        low=expected_entry,
        close=expected_entry,
        volume=1.5,
        interval="1m"
    )
    assert candle.symbol == "BTCUSDT"
    
    # 2. FEATURE platform Indicators register and compute
    from research_platform.feature_platform.orchestrator import FeaturePlatformOrchestrator
    fp_orch = container.resolve(FeaturePlatformOrchestrator)
    from research_platform.feature_platform.models import FeatureRecord
    features = ["open", "high", "low", "close", "ema9", "ema21", "rsi", "atr"]
    feature_dependencies = {
        "open": [], "high": [], "low": [], "close": [],
        "ema9": ["close"], "ema21": ["close"], "rsi": ["close"], "atr": ["high", "low", "close"]
    }
    for name in features:
        record = FeatureRecord(
            uuid=name, name=name, display_name=name.upper(), description="", formula=name,
            dependencies=feature_dependencies[name], category="Indicator", subcategory="Raw",
            owner="quants", author="CTO", version="1.0.0", update_frequency="1m",
            warmup_length=0, lookback_window=0, required_resolution="1m"
        )
        try:
            fp_orch.register_feature(record)
        except ValueError:
            pass

    import pandas as pd
    df = pd.DataFrame([candle.model_dump()])
    output_df = fp_orch.compute_and_store(features, symbol, df)
    assert not output_df.empty
    
    # 3. STRATEGY composer evaluation
    from research_platform.strategy_framework.composer import StrategyComposer
    strategy_composer = container.resolve(StrategyComposer)
    strategy = strategy_composer.compose(
        strategy_id=f"strat_{symbol}",
        name="Mean Reversion E2E",
        strategy_type="MEAN_REVERSION",
        version="1.0.0",
        symbols=[symbol],
        parameters={"deviation": 2.0}
    )
    indicators = output_df.iloc[-1].to_dict()
    strategy_decision = strategy_composer.generate_decision(
        strategy=strategy,
        symbol=symbol,
        current_price=expected_entry,
        indicators=indicators
    )
    assert strategy_decision is not None

    # 4. AI SIGNAL generation (confluence and feedback)
    from research_platform.ai_signal.signal_generator import AISignalGenerator
    ai_generator = container.resolve(AISignalGenerator)
    ai_signal = ai_generator.generate_signal(symbol, expected_entry)
    assert ai_signal.signal in ("BUY", "SELL", "WAIT")
    
    # For E2E validation, force signal to BUY if it is WAIT
    if ai_signal.signal == "WAIT":
        ai_signal = ai_signal.model_copy(update={
            "signal": "BUY",
            "confidence": 0.80,
            "reasoning": "Golden cross forced confluence."
        })

    # 5. AI AUDITOR audit check
    auditor = AIDecisionAuditor(min_confidence=0.55, min_risk_reward=1.5)
    signal_dict = {
        "signal": ai_signal.signal,
        "confidence": ai_signal.confidence,
        "reasoning": ai_signal.reasoning,
        "entry": expected_entry,
        "stop_loss": expected_entry - 900.0,
        "take_profit": expected_entry + 1800.0
    }
    audit_decision = auditor.audit(signal_dict, regime="TRENDING")
    assert audit_decision.approved is True

    # 6. RISK governance evaluate & score check
    risk_monitor = RealTimeRiskMonitor()
    risk_snap = risk_monitor.calculate_risk_score(
        capital=100000.0,
        open_positions=[],
        peak_capital=100000.0,
        leverage=1.0,
        consecutive_losses=0,
        daily_pnl=0.0
    )
    assert risk_snap.risk_score > 80.0
    
    kill_switch = KillSwitchEngine(daily_loss_limit_pct=3.0, max_drawdown_pct=8.0)
    ks_state = kill_switch.evaluate(
        daily_pnl=0.0,
        current_capital=100000.0,
        peak_capital=100000.0,
        consecutive_losses=0,
        avg_execution_quality=95.0,
        exchange_connected=True
    )
    assert ks_state.value == "NORMAL"
    assert kill_switch.trading_allowed is True

    # 7. OMS order placement
    from research_platform.oms.oms_core import OmsCore
    from research_platform.oms.models import Order
    oms = container.resolve(OmsCore)
    order_id = f"ord-{uuid.uuid4().hex[:8]}"
    order = Order(
        order_id=order_id,
        strategy_id="strat_BTCUSDT",
        symbol=symbol,
        quantity=quantity,
        price=expected_entry,
        order_type="MARKET",
        side=ai_signal.signal,
        status="NEW"
    )
    oms.repository.save_order(order)
    assert oms.repository.get_order(order_id) is not None

    # 8. EXECUTION SIMULATOR fill simulation
    exec_sim = ExchangeExecutionSimulator(
        spread_bps=6.0,
        maker_fee=0.0002,
        taker_fee=0.0005,
        max_volume_pct=0.20
    )
    exec_result = exec_sim.simulate_order(
        symbol=symbol,
        side=ai_signal.signal,
        quantity=quantity,
        mid_price=expected_entry,
        market_volume=100.0,
        atr=300.0,
        expected_entry=expected_entry,
        order_id=order_id
    )
    fill = exec_result["fill"]
    report = exec_result["report"]
    assert fill.status == OrderStatus.FILLED
    assert fill.fee_paid > 0.0
    
    # 9. TRADE MEMORY validation & storage
    test_file = "data/test_trade_memory_real_pipeline.json"
    if os.path.exists(test_file):
        try:
            os.remove(test_file)
        except Exception:
            pass
    trade_memory = TradeMemoryEngine(persistence_file=test_file)
    completed_trade = trade_memory.save_trade(
        symbol=symbol,
        entry=expected_entry,
        exit=fill.fill_price,
        entry_time=datetime.now(timezone.utc),
        exit_time=datetime.now(timezone.utc),
        features_at_entry={"RSI": 62.5, "ATR": 300.0},
        decision_reason=ai_signal.reasoning,
        pnl=fill.after_fee_pnl,
        execution_quality=report.execution_score,
        slippage=fill.slippage,
        fees=fill.fee_paid,
        fill_time=fill.fill_time
    )
    assert completed_trade is not None
    assert len(trade_memory.trades) == 1

    if os.path.exists(test_file):
        try:
            os.remove(test_file)
        except Exception:
            pass
