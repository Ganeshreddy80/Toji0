"""Thread-safe Price Action Feature Store implementing IPriceActionFeatureStore."""

from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

from price_action.core.interfaces import IPriceActionFeatureStore
from price_action.core.models import (
    MultiTimeframePriceActionSnapshot,
    PriceActionFeatures,
)

logger = logging.getLogger(__name__)


class PriceActionFeatureStore(IPriceActionFeatureStore):
    """Thread-safe in-memory feature store for price action market intelligence."""

    def __init__(self, history_limit: int = 100) -> None:
        self._lock = threading.Lock()
        self._history_limit = history_limit
        self._snapshots: Dict[str, MultiTimeframePriceActionSnapshot] = {}

    def store_snapshot(self, snapshot: MultiTimeframePriceActionSnapshot) -> None:
        """Store a multi-timeframe price action snapshot thread-safely."""
        if not snapshot or not snapshot.symbol:
            return

        with self._lock:
            symbol = snapshot.symbol
            self._snapshots[symbol] = snapshot
            logger.debug("PriceActionFeatureStore: Stored snapshot for '%s'", symbol)

    def get_latest_snapshot(self, symbol: str) -> Optional[MultiTimeframePriceActionSnapshot]:
        """Fetch the latest multi-timeframe price action snapshot for a symbol."""
        with self._lock:
            return self._snapshots.get(symbol)

    def get_features(self, symbol: str, timeframe: str = "1h") -> Optional[PriceActionFeatures]:
        """Flatten and extract derived price action features for a symbol and timeframe."""
        with self._lock:
            snap = self._snapshots.get(symbol)
            if not snap:
                return None

            tf_snap = snap.timeframe_snapshots.get(timeframe)
            if not tf_snap:
                # Fallback to any available timeframe snapshot
                if snap.timeframe_snapshots:
                    tf_snap = next(iter(snap.timeframe_snapshots.values()))
                else:
                    return None

            feat_dict: Dict[str, float | str | bool] = {
                "symbol": snap.symbol,
                "timeframe": tf_snap.timeframe,
                "primary_regime": snap.primary_regime.value,
                "primary_trend": snap.primary_trend.value,
                "confluence_score": snap.confluence_score,
                "trend_direction": tf_snap.trend.direction.value,
                "trend_strength": tf_snap.trend.strength,
                "trend_aligned": tf_snap.trend.is_aligned,
                "atr": tf_snap.volatility.atr,
                "atr_percent": tf_snap.volatility.atr_percent,
                "bb_bandwidth": tf_snap.volatility.bb_bandwidth,
                "is_squeeze": tf_snap.volatility.is_squeeze,
                "rsi": tf_snap.momentum.rsi,
                "macd": tf_snap.momentum.macd,
                "macd_histogram": tf_snap.momentum.macd_histogram,
                "divergence": tf_snap.momentum.divergence.value,
                "market_structure_bias": tf_snap.market_structure.trend_bias.value,
                "swing_count": len(tf_snap.swings),
                "liquidity_pool_count": len(tf_snap.liquidity_pools),
                "fvg_count": len(tf_snap.fvgs),
                "unmitigated_fvg_count": len([f for f in tf_snap.fvgs if not f.is_mitigated]),
                "order_block_count": len(tf_snap.order_blocks),
                "unmitigated_ob_count": len([ob for ob in tf_snap.order_blocks if not ob.is_mitigated]),
                "current_zone": tf_snap.premium_discount.current_zone.value if tf_snap.premium_discount else "EQUILIBRIUM",
                "regime": tf_snap.regime.regime.value,
                "regime_confidence": tf_snap.regime.confidence,
            }

            return PriceActionFeatures(
                symbol=symbol,
                timeframe=tf_snap.timeframe,
                timestamp=snap.timestamp,
                features=feat_dict,
            )

    def clear(self) -> None:
        """Purge stored feature store data."""
        with self._lock:
            self._snapshots.clear()
            logger.debug("PriceActionFeatureStore: Cleared memory.")
