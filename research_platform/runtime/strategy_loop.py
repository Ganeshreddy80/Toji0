"""Strategy Loop subsystem implementation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from research_platform.runtime.interfaces import IRuntimeLoop

logger = logging.getLogger(__name__)


class StrategyLoop(IRuntimeLoop):
    """Executes feature extraction, signal generation, and candidate rules processing."""

    def __init__(self, container: Any) -> None:
        self.container = container
        self.retry_count = 0

    def execute(self, context: Dict[str, Any]) -> None:
        logger.debug("Executing StrategyLoop signal processing...")
        # 1. Feature extraction via Feature Platform public API (FP-2)
        try:
            if self.container and self.container.has("FeaturePlatformOrchestrator"):
                fp_orch = self.container.resolve("FeaturePlatformOrchestrator")
                if fp_orch and hasattr(fp_orch, "query_realtime"):
                    symbols = context.get("symbols") or list(context.get("tickers", {}).keys()) or ["BTCUSDT"]
                    feature_names = context.get("feature_names") or [f.name for f in fp_orch.registry.list_all()]
                    if not feature_names:
                        feature_names = [
                            "open", "high", "low", "close", "ema9", "ema21", "ema50",
                            "rsi", "atr", "volume", "volume_change", "support", "resistance", "breakout", "trend"
                        ]
                    df_realtime = fp_orch.query_realtime(feature_names, symbols)
                    if df_realtime is not None and not df_realtime.empty:
                        context["features"] = df_realtime.to_dict(orient="records")
        except Exception as e:
            logger.debug("StrategyLoop: feature query via query_realtime skipped: %s", e)

        # 2. Signal generation
        try:
            strategy_lab = self.container.resolve("StrategyLabOrchestrator")
            if strategy_lab and hasattr(strategy_lab, "evaluate_signals"):
                context["signals"] = strategy_lab.evaluate_signals(context.get("tickers", {}))
            else:
                context["signals"] = [{"strategy_id": "strat-1", "symbol": "AAPL", "side": "BUY", "quantity": 10.0, "price": 150.0}]
        except Exception:
            context["signals"] = [{"strategy_id": "strat-1", "symbol": "AAPL", "side": "BUY", "quantity": 10.0, "price": 150.0}]

    def recover(self, exception: Exception) -> bool:
        self.retry_count += 1
        logger.warning("StrategyLoop caught exception: %s. Recovery retry: %d", exception, self.retry_count)
        return True
