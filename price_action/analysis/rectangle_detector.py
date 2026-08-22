"""Rectangle Continuation Pattern Detector for identifying consolidation channels."""

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
from price_action.utils.tolerance import is_horizontal
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


class RectangleDetector(IPatternDetector):
    """Detects Rectangle continuation patterns bounded by parallel horizontal support and resistance."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "rectangle_detector"

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
        first_swing = swings_subset[0]
        second_swing = swings_subset[1]

        # Preceding move direction
        preceding_bullish = second_swing.price > first_swing.price

        consolidation_swings = swings_subset[1:]
        highs, lows = partition_highs_lows(consolidation_swings)

        if len(highs) < 2 or len(lows) < 2:
            return None, None

        p_highs = [
            PatternPoint(price=h.price, timestamp=h.timestamp, index=h.index, point_label="High")
            for h in highs
        ]
        p_lows = [
            PatternPoint(price=l.price, timestamp=l.timestamp, index=l.index, point_label="Low")
            for l in lows
        ]

        slope_high, intercept_high, r2_high = fit_line(p_highs)
        slope_low, intercept_low, r2_low = fit_line(p_lows)

        slope_high_norm = normalize_slope(slope_high, atr)
        slope_low_norm = normalize_slope(slope_low, atr)

        pattern_type = None
        direction = PatternDirection.NEUTRAL

        # Rectangle: both boundaries must be horizontal
        if is_horizontal(slope_high_norm, 0.03) and is_horizontal(slope_low_norm, 0.03):
            pattern_type = PatternType.RECTANGLE
            direction = PatternDirection.BULLISH if preceding_bullish else PatternDirection.BEARISH

        if pattern_type is None:
            return None, None

        left_width = abs(highs[-1].index - highs[0].index)
        right_width = abs(lows[-1].index - lows[0].index)
        symmetry = calculate_symmetry_score(left_width, right_width)

        min_p, max_p = get_extremes(swings_subset)
        height = max_p - min_p
        atr_norm = calculate_atr_normalization(height, atr)

        fit_score = calculate_fit_score(r2_high, r2_low)
        geom = calculate_geometry_score(fit_score)
        vol_score = 1.0

        overall = calculate_overall_score(geom, symmetry, fit_score, vol_score, atr_norm)

        upper_trend = Trendline(
            start_point=p_highs[0], end_point=p_highs[-1], slope=slope_high, intercept=intercept_high
        )
        lower_trend = Trendline(
            start_point=p_lows[0], end_point=p_lows[-1], slope=slope_low, intercept=intercept_low
        )

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        meta = PatternMetadata(
            source_engine=self.detector_id,
            version="1.0.0",
            parameters={"preceding_bullish": preceding_bullish},
            quality_score=overall,
            geometry_score=geom,
            symmetry_score=symmetry,
            touch_count=4,
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        candidate = PatternCandidate(
            candidate_id=f"cand-rect-{symbol}-{timeframe}-{highs[-1].index}",
            symbol=symbol,
            timeframe=timeframe,
            pattern_type=pattern_type,
            direction=direction,
            points=p_highs + p_lows,
            trendlines=[upper_trend, lower_trend],
            score=overall,
            detected_at=ts,
            metadata=meta,
        )

        match = None
        if latest_swing is not None:
            upper_val = line_value(slope_high, intercept_high, latest_swing.index)
            lower_val = line_value(slope_low, intercept_low, latest_swing.index)

            is_bullish_break, is_bearish_break = evaluate_breakout(latest_swing.price, upper_val, lower_val)

            confirmed = False
            if direction == PatternDirection.BULLISH and is_bullish_break:
                confirmed = True
            elif direction == PatternDirection.BEARISH and is_bearish_break:
                confirmed = True

            if confirmed:
                match = PatternMatch(
                    match_id=f"match-rect-{symbol}-{timeframe}-{latest_swing.index}",
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_type=pattern_type,
                    direction=direction,
                    status=PatternStatus.CONFIRMED,
                    points=p_highs + p_lows,
                    trendlines=[upper_trend, lower_trend],
                    fit_score=overall,
                    confirmed_at=ts,
                    metadata=meta,
                )

        return candidate, match
