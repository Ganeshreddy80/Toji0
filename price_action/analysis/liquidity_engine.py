"""Liquidity engine detecting BSL, SSL, equal highs/lows, and liquidity sweeps."""

from __future__ import annotations

import logging
import uuid
from typing import List

from price_action.core.enums import LiquidityType, SwingType
from price_action.core.interfaces import ILiquidityEngine
from price_action.core.models import (
    LiquidityPool,
    PriceActionBar,
    PriceActionConfig,
    PriceActionSwing,
)

logger = logging.getLogger(__name__)


class LiquidityEngine(ILiquidityEngine):
    """Detects Buy-Side Liquidity (BSL), Sell-Side Liquidity (SSL), and liquidity sweeps."""

    def detect_liquidity(
        self, bars: List[PriceActionBar], swings: List[PriceActionSwing], config: PriceActionConfig | None = None
    ) -> List[LiquidityPool]:
        """Identify liquidity pools above swing highs and below swing lows, plus sweeps."""
        if not swings or not bars:
            return []

        cfg = config or PriceActionConfig()
        tol = cfg.liquidity_tolerance_pct
        pools: List[LiquidityPool] = []
        last_bar = bars[-1]

        # 1. BSL Pools (Swing Highs)
        swing_highs = [s for s in swings if s.swing_type == SwingType.SWING_HIGH]
        for sh in swing_highs:
            touches = sum(1 for s in swing_highs if abs(s.price - sh.price) / sh.price <= tol)
            # Check if swept by recent candle highs
            is_swept = last_bar.high > sh.price and last_bar.close < sh.price
            pools.append(
                LiquidityPool(
                    pool_id=f"bsl-{sh.index}-{int(sh.price)}",
                    liquidity_type=LiquidityType.BSL,
                    price_level=sh.price,
                    touches=touches,
                    is_swept=is_swept,
                    swept_at=last_bar.timestamp if is_swept else None,
                )
            )

        # 2. SSL Pools (Swing Lows)
        swing_lows = [s for s in swings if s.swing_type == SwingType.SWING_LOW]
        for sl in swing_lows:
            touches = sum(1 for s in swing_lows if abs(s.price - sl.price) / sl.price <= tol)
            # Check if swept by recent candle lows
            is_swept = last_bar.low < sl.price and last_bar.close > sl.price
            pools.append(
                LiquidityPool(
                    pool_id=f"ssl-{sl.index}-{int(sl.price)}",
                    liquidity_type=LiquidityType.SSL,
                    price_level=sl.price,
                    touches=touches,
                    is_swept=is_swept,
                    swept_at=last_bar.timestamp if is_swept else None,
                )
            )

        return pools
