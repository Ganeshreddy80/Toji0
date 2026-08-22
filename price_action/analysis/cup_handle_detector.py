"""Cup & Handle Pattern Detector for identifying rounding bottoms with consolidation handles."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from market_intelligence.core.enums import SwingType
from market_intelligence.core.models import SwingPoint, MarketState
from price_action.core.enums import PatternDirection, PatternStatus, PatternType
from price_action.core.interfaces import IPatternDetector
from price_action.core.models import (
    DetectorContext,
    PatternCandidate,
    PatternMatch,
    PatternPoint,
    PatternMetadata,
    Trendline,
)
from price_action.utils.regression import fit_line
from price_action.utils.geometry import line_value
from price_action.utils.statistics import calculate_fit_score, normalize_slope
from price_action.utils.projection import check_breakout
from price_action.utils.swing_selection import select_recent_swings, partition_highs_lows, get_extremes
from price_action.utils.pattern_score import (
    calculate_geometry_score,
    calculate_symmetry_score,
    calculate_volume_confirmation,
    calculate_atr_normalization,
    calculate_overall_score,
)
from price_action.utils.breakout import evaluate_breakout
from toji_platform.core.dependency_injection.interfaces import IContainer

logger = logging.getLogger(__name__)


class CupHandleDetector(IPatternDetector):
    """Detects Cup & Handle bullish continuation chart patterns."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "cup_handle_detector"

    def detect(self, context: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        if not isinstance(context, DetectorContext):
            context = DetectorContext.from_market_state(context)

        symbol = context.market_state.symbol
        timeframe = context.timeframe
        swings = context.swings
        atr = context.atr

        if len(swings) < 5:
            return [], []

        recent_swings = select_recent_swings(swings, count=6)
        candidates = []
        matches = []
        ts = getattr(context.market_state, "updated_at", datetime.now(timezone.utc))

        # Pass 1: Fit on recent_swings[:-1] to check breakout on the latest swing point
        if len(recent_swings) >= 6:
            cand_pre, match_breakout = self._detect_from_subset(
                symbol, timeframe, recent_swings[:-1], recent_swings[-1], atr, ts
            )
            if match_breakout is not None:
                matches.append(match_breakout)
                if cand_pre is not None:
                    candidates.append(cand_pre)
                return candidates, matches

        # Pass 2: Fit on all recent swings to check for a developing candidate
        cand_all, _ = self._detect_from_subset(
            symbol, timeframe, recent_swings, None, atr, ts
        )
        if cand_all is not None:
            candidates.append(cand_all)

        return candidates, matches

    def _detect_from_subset(
        self,
        symbol: str,
        timeframe: str,
        swings_subset: list[SwingPoint],
        latest_swing: SwingPoint | None = None,
        atr: float = 0.0,
        timestamp: datetime | None = None,
    ) -> tuple[PatternCandidate | None, PatternMatch | None]:
        highs, lows = partition_highs_lows(swings_subset)

        # We need Lip 1 (High), Bottom (Low), Lip 2 (High), Handle Low (Low)
        if len(highs) < 2 or len(lows) < 2:
            return None, None

        lip1 = highs[-2]
        lip2 = highs[-1]
        bottom = lows[-2]
        handle_low = lows[-1]

        # Validations:
        # 1. Cup bottom must be significantly below lips
        # 2. Lip prices must be approximately equal (within 0.15 ATR or 1.5% of average price)
        # 3. Handle low must be below Lip 2 but above Cup bottom
        avg_lip_price = (lip1.price + lip2.price) / 2.0
        lip_diff = abs(lip1.price - lip2.price)

        is_valid_cup = (
            bottom.price < lip1.price and
            bottom.price < lip2.price and
            lip_diff <= (atr * 1.5 if atr > 0.0 else avg_lip_price * 0.03) and
            handle_low.price > bottom.price and
            handle_low.price < lip2.price
        )

        if not is_valid_cup:
            return None, None

        pattern_type = PatternType.CUP_AND_HANDLE
        direction = PatternDirection.BULLISH

        p_points = [
            PatternPoint(price=lip1.price, timestamp=lip1.timestamp, index=lip1.index, point_label="LeftLip"),
            PatternPoint(price=bottom.price, timestamp=bottom.timestamp, index=bottom.index, point_label="CupBottom"),
            PatternPoint(price=lip2.price, timestamp=lip2.timestamp, index=lip2.index, point_label="RightLip"),
            PatternPoint(price=handle_low.price, timestamp=handle_low.timestamp, index=handle_low.index, point_label="HandleLow"),
        ]

        # Symmetry: compare cup width to handle width
        cup_width = abs(lip2.index - lip1.index)
        handle_width = abs(handle_low.index - lip2.index)
        symmetry = calculate_symmetry_score(cup_width, handle_width * 3)  # handle is usually ~1/3 of cup

        min_p, max_p = get_extremes(swings_subset)
        height = max_p - min_p
        atr_norm = calculate_atr_normalization(height, atr)

        fit_score = 1.0
        geom = calculate_geometry_score(fit_score)
        vol_score = 1.0

        overall = calculate_overall_score(geom, symmetry, fit_score, vol_score, atr_norm)

        trendlines = [
            Trendline(start_point=p_points[0], end_point=p_points[2], slope=0.0, intercept=avg_lip_price)
        ]

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        meta = PatternMetadata(
            source_engine=self.detector_id,
            version="1.0.0",
            parameters={"cup_width": cup_width, "handle_width": handle_width},
            quality_score=overall,
            geometry_score=geom,
            symmetry_score=symmetry,
            touch_count=4,
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        candidate = PatternCandidate(
            candidate_id=f"cand-cuphandle-{symbol}-{timeframe}-{lip2.index}",
            symbol=symbol,
            timeframe=timeframe,
            pattern_type=pattern_type,
            direction=direction,
            points=p_points,
            trendlines=trendlines,
            score=overall,
            detected_at=ts,
            metadata=meta,
        )

        match = None
        if latest_swing is not None:
            # Breakout level is the right lip price
            breakout_level = lip2.price

            is_bullish_break, _ = evaluate_breakout(latest_swing.price, breakout_level, breakout_level)

            if is_bullish_break:
                match = PatternMatch(
                    match_id=f"match-cuphandle-{symbol}-{timeframe}-{latest_swing.index}",
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_type=pattern_type,
                    direction=direction,
                    status=PatternStatus.CONFIRMED,
                    points=p_points,
                    trendlines=trendlines,
                    fit_score=overall,
                    confirmed_at=ts,
                    metadata=meta,
                )

        return candidate, match
