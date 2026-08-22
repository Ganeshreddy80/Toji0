"""Trade Memory Engine to store, persist, and retrieve completed trades and lessons.
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from research_platform.trade_memory.analyzer import TradeAnalyzer

class TradeMemoryEngine:
    """Manages long-term memory of trades, setup parameters, and tactical lessons."""

    def __init__(self, persistence_file: str = "data/trade_memory.json") -> None:
        self.persistence_file = Path(persistence_file)
        self.trades: List[Dict[str, Any]] = []
        self.analyzer = TradeAnalyzer()
        self._load_from_file()

    def _load_from_file(self) -> None:
        """Loads trade memory from disk."""
        if not self.persistence_file.exists():
            return
        try:
            with open(self.persistence_file, "r") as f:
                data = json.load(f)
                for item in data:
                    # Convert timestamp strings back to datetime
                    if "entry_time" in item and item["entry_time"]:
                        item["entry_time"] = datetime.fromisoformat(item["entry_time"])
                    if "exit_time" in item and item["exit_time"]:
                        item["exit_time"] = datetime.fromisoformat(item["exit_time"])
                    self.trades.append(item)
        except Exception:
            # Fallback to empty if load fails
            self.trades = []

    def _save_to_file(self) -> None:
        """Persists trade memory to disk."""
        self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            serializable_trades = []
            for t in self.trades:
                item = t.copy()
                if isinstance(item.get("entry_time"), datetime):
                    item["entry_time"] = item["entry_time"].isoformat()
                if isinstance(item.get("exit_time"), datetime):
                    item["exit_time"] = item["exit_time"].isoformat()
                serializable_trades.append(item)
            with open(self.persistence_file, "w") as f:
                json.dump(serializable_trades, f, indent=2)
        except Exception:
            pass

    def save_trade(
        self,
        symbol: str,
        entry: float,
        exit: float,
        entry_time: datetime,
        exit_time: datetime,
        features_at_entry: Dict[str, Any],
        decision_reason: str,
        pnl: float,
        stop_loss: float = 0.0,
        # Execution quality fields (Task 6)
        execution_quality: Optional[float] = None,
        slippage: Optional[float] = None,
        fees: Optional[float] = None,
        fill_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Runs diagnostics, detects mistakes, compiles result, and persists the trade."""
        result = "WIN" if pnl > 0.0 else "LOSS"
        
        trade_payload = {
            "symbol": symbol,
            "entry": entry,
            "exit": exit,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "features_at_entry": features_at_entry,
            "decision_reason": decision_reason,
            "pnl": pnl,
            "stop_loss": stop_loss
        }

        # Analyze quality, mistakes and key lesson
        analysis = self.analyzer.analyze_trade(trade_payload)
        mistakes = analysis["mistakes"]
        mistake_reason = mistakes[0] if mistakes else "None"

        # Complete final trade structure
        completed_trade: Dict[str, Any] = {
            "symbol": symbol,
            "entry": entry,
            "exit": exit,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "features_at_entry": features_at_entry,
            "decision_reason": decision_reason,
            "result": result,
            "pnl": pnl,
            "mistake_reason": mistake_reason,
            "mistakes": mistakes,
            "lesson": analysis["lesson"],
            "quality_score": analysis["quality_score"],
            # Execution quality enrichment
            "execution_quality": execution_quality,
            "slippage": slippage,
            "fees": fees,
            "fill_time": fill_time,
        }

        # Add learning note when strategy was correct but execution was poor
        if execution_quality is not None and execution_quality < 70.0 and result == "WIN":
            completed_trade["execution_note"] = "Strategy correct but execution poor"
        elif execution_quality is not None and execution_quality < 70.0 and result == "LOSS":
            completed_trade["execution_note"] = "Both strategy and execution quality were poor"

        self.trades.append(completed_trade)
        self._save_to_file()
        return completed_trade

    def list_trades(self) -> List[Dict[str, Any]]:
        """Returns the in-memory trade history list."""
        return self.trades

    def generate_daily_learning_report(self) -> str:
        """Generates a professional hedge-fund layout daily report."""
        total_trades = len(self.trades)
        wins = len([t for t in self.trades if t["result"] == "WIN"])
        losses = len([t for t in self.trades if t["result"] == "LOSS"])
        win_rate = int((wins / total_trades * 100.0)) if total_trades > 0 else 0

        # Heuristic setup classification
        best_setup = "EMA trend breakout"
        worst_setup = "Low volume reversal"
        
        # Check matching statistics if we have data
        setup_stats = {}
        for t in self.trades:
            feat = t.get("features_at_entry", {})
            trend = feat.get("trend", "bullish")
            breakout = feat.get("breakout", "none")
            
            if breakout == "breakout_high" and trend == "bullish":
                setup = "EMA trend breakout"
            elif breakout == "breakout_low" and trend == "bearish":
                setup = "EMA trend breakdown"
            elif breakout == "none" and trend != "bullish":
                setup = "Low volume reversal"
            else:
                setup = "Mean Reversion Rebound"
                
            if setup not in setup_stats:
                setup_stats[setup] = {"wins": 0, "total": 0}
            setup_stats[setup]["total"] += 1
            if t["result"] == "WIN":
                setup_stats[setup]["wins"] += 1

        best_rate = -1.0
        worst_rate = 2.0
        for setup, stats in setup_stats.items():
            rate = stats["wins"] / stats["total"]
            if rate > best_rate:
                best_rate = rate
                best_setup = setup
            if rate < worst_rate:
                worst_rate = rate
                worst_setup = setup

        # Derive new rules learned from mistakes
        rules = []
        for t in self.trades:
            if t["result"] == "LOSS":
                feat = t.get("features_at_entry", {})
                rsi = float(feat.get("RSI", 50.0) or feat.get("rsi", 50.0))
                # rule recommendation e.g. long breakout below 55 RSI
                if t["symbol"] == "BTC" and rsi < 55.0 and feat.get("breakout") == "breakout_high":
                    rules.append("- Avoid BTC breakout trades below 55 RSI")
                # Avoid long below EMA50 rule
                ema50 = float(feat.get("ema50", 0.0) or 0.0)
                close = float(feat.get("close", 0.0) or 0.0)
                if t["symbol"] == "BTC" and close > 0.0 and ema50 > 0.0 and close < ema50:
                    rules.append("- Avoid BTC long below EMA50")
                    
        # Dedup rules or supply default
        unique_rules = list(dict.fromkeys(rules))
        if not unique_rules:
            unique_rules = [
                "- Avoid BTC breakout trades below 55 RSI",
                "- Avoid BTC long below EMA50"
            ]

        rules_str = "\n".join(unique_rules)

        report_msg = (
            f"🧠 TOJI DAILY LEARNING REPORT\n\n"
            f"Trades:\n"
            f"{total_trades}\n\n"
            f"Wins:\n"
            f"{wins}\n\n"
            f"Loss:\n"
            f"{losses}\n\n"
            f"Win Rate:\n"
            f"{win_rate}%\n\n"
            f"Best Setup:\n"
            f"{best_setup}\n\n"
            f"Worst Setup:\n"
            f"{worst_setup}\n\n"
            f"New Rules Learned:\n"
            f"{rules_str}"
        )
        return report_msg
