"""Historical event replay backtesting engine using live pipeline modules.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from research_platform.platform.service_registry import ServiceRegistry
from research_platform.feature_platform.feature_pipeline import FeaturePipeline
from research_platform.feature_platform.dependency_graph import DependencyGraph
from research_platform.strategy_framework.composer import StrategyComposer

class HistoricalReplayEngine:
    """Replays historical market ticks using live feature, strategy, and risk modules."""

    def __init__(self, data_df: pd.DataFrame, strategy_name: str = "EMA Breakout") -> None:
        self.data_df = data_df.copy()
        if "timestamp" in self.data_df.columns:
            self.data_df["timestamp"] = pd.to_datetime(self.data_df["timestamp"])
            self.data_df = self.data_df.sort_values("timestamp").reset_index(drop=True)
            
        self.strategy_name = strategy_name
        self.strategy_composer = StrategyComposer()
        
        # Instantiate same live Feature Engine with populated dependency graph
        self.dep_graph = DependencyGraph()
        feature_dependencies = {
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
            "ema9": ["close"],
            "ema21": ["close"],
            "ema50": ["close"],
            "rsi": ["close"],
            "atr": ["high", "low", "close"],
            "volume_change": ["volume"],
            "support": ["low"],
            "resistance": ["high"],
            "breakout": ["close", "resistance", "support"],
            "trend": ["ema9", "ema21"]
        }
        for name, deps in feature_dependencies.items():
            self.dep_graph.add_node(name, deps)
            
        self.feature_pipeline = FeaturePipeline(self.dep_graph)

    def run_backtest(self, initial_capital: float = 100000.0) -> Dict[str, Any]:
        """Runs the historical backtest simulation and outputs performance statistics."""
        # 1. Calculate identical feature engine features
        features_to_compute = [
            "open", "high", "low", "close", "ema9", "ema21", "ema50",
            "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
        ]
        
        # Ensure input data has necessary base columns
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in self.data_df.columns:
                self.data_df[col] = 100.0  # fallback baseline
                
        computed_df = self.feature_pipeline.compute(features_to_compute, self.data_df)

        # 2. Replay simulation
        balance = initial_capital
        peak_balance = initial_capital
        max_drawdown = 0.0
        
        trades_count = 0
        wins = 0
        losses = 0
        total_profit = 0.0
        total_loss = 0.0
        trade_pnls = []
        
        position = None  # None or Dict representing active long position
        
        for idx in range(len(computed_df)):
            row = computed_df.iloc[idx]
            current_price = float(row["close"])
            current_time = row["timestamp"]
            
            # Update peak and drawdown
            current_equity = balance
            if position:
                pos_pnl = position["quantity"] * (current_price - position["entry_price"])
                current_equity += pos_pnl
            
            if current_equity > peak_balance:
                peak_balance = current_equity
            
            dd = (peak_balance - current_equity) / peak_balance if peak_balance > 0 else 0.0
            if dd > max_drawdown:
                max_drawdown = dd
                
            # Get current features dict
            feat_dict = {
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "ema9": row["ema9"],
                "ema21": row["ema21"],
                "ema50": row["ema50"],
                "rsi": row["rsi"],
                "atr": row["atr"],
                "volume_change": row["volume_change"],
                "support": row["support"],
                "resistance": row["resistance"],
                "breakout": row["breakout"],
                "trend": row["trend"]
            }

            # Strategy decision
            composed_strategy = self.strategy_composer.compose(
                strategy_id="strat_backtest",
                name=self.strategy_name,
                strategy_type="BREAKOUT" if "breakout" in self.strategy_name.lower() else "MEAN_REVERSION",
                version="1.0.0",
                symbols=["BTCUSDT"],
                parameters={"deviation": 2.0}
            )
            
            # Evaluate using identical Strategy Engine
            decision_str = self.strategy_composer.evaluate_strategy(
                composed_strategy, "BTCUSDT", current_price, feat_dict
            )
            
            # Position management rules
            if position:
                # Check Stop Loss / Take Profit
                sl_hit = current_price <= position["sl"]
                tp_hit = current_price >= position["tp"]
                exit_signal = decision_str == "SELL"
                
                if sl_hit or tp_hit or exit_signal:
                    # Exit position
                    exit_price = position["sl"] if sl_hit else (position["tp"] if tp_hit else current_price)
                    pnl = position["quantity"] * (exit_price - position["entry_price"])
                    
                    balance += pnl
                    trades_count += 1
                    trade_pnls.append(pnl)
                    if pnl > 0:
                        wins += 1
                        total_profit += pnl
                    else:
                        losses += 1
                        total_loss += abs(pnl)
                        
                    position = None
            else:
                # Check entry
                if decision_str == "BUY":
                    # Enter virtual LONG order
                    atr_val = feat_dict["atr"] if feat_dict["atr"] > 0 else current_price * 0.01
                    sl = current_price - (1.5 * atr_val)
                    tp = current_price + (3.0 * atr_val)
                    
                    quantity = (balance * 0.05) / current_price  # 5% capital sizing
                    position = {
                        "entry_price": current_price,
                        "quantity": quantity,
                        "sl": sl,
                        "tp": tp,
                        "entry_time": current_time,
                        "features_at_entry": feat_dict
                    }

        # Calculate metrics
        win_rate = int((wins / trades_count * 100)) if trades_count > 0 else 0
        profit_factor = round(total_profit / total_loss, 1) if total_loss > 0 else (round(total_profit, 1) if total_profit > 0 else 1.0)
        drawdown_pct = int(max_drawdown * 100)

        # Print layout exactly as requested
        print(f"\nStrategy:")
        print(f"{self.strategy_name}")
        print(f"\n{trades_count} trades tested")
        print(f"\nWin rate:")
        print(f"{win_rate}%")
        print(f"\nProfit Factor:")
        print(f"{profit_factor}")
        print(f"\nMax Drawdown:")
        print(f"{drawdown_pct}%")

        return {
            "strategy": self.strategy_name,
            "trades_tested": trades_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "max_drawdown": drawdown_pct,
            "trade_pnls": trade_pnls
        }
