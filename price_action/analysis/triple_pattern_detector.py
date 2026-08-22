"""Triple Pattern Detector for identifying Triple Tops and Triple Bottoms."""

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


class TriplePatternDetector(IPatternDetector):
    """Detects Triple Top and Triple Bottom reversal chart patterns."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "triple_pattern_detector"

    def detect(self, context: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        if not isinstance(context, DetectorContext):
            context = DetectorContext.from_market_state(context)

        symbol = context.market_state.symbol
        timeframe = context.timeframe
        swings = context.swings
        atr = context.atr

        # We need at least 5 swing points to define a triple top or bottom
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

        pattern_type = None
        direction = PatternDirection.NEUTRAL

        p_points = []
        trendlines = []
        r2_high, r2_low = 1.0, 1.0
        slope_high, intercept_high = 0.0, 0.0
        slope_low, intercept_low = 0.0, 0.0

        # Triple Top: 3 Highs (Peaks), 2 intervening Lows (Neckline Troughs)
        if len(highs) >= 3 and len(lows) >= 2:
            p_highs = [
                PatternPoint(price=h.price, timestamp=h.timestamp, index=h.index, point_label="High")
                for h in highs[-3:]
            ]
            p_lows = [
                PatternPoint(price=l.price, timestamp=l.timestamp, index=l.index, point_label="Neckline")
                for l in lows[-2:]
            ]

            slope_high, intercept_high, r2_high = fit_line(p_highs)
            slope_high_norm = normalize_slope(slope_high, atr)

            if is_horizontal(slope_high_norm, threshold=0.03):
                pattern_type = PatternType.TRIPLE_TOP
                direction = PatternDirection.BEARISH
                p_points = p_highs + p_lows
                trendlines = [
                    Trendline(start_point=p_highs[0], end_point=p_highs[-1], slope=slope_high, intercept=intercept_high)
                ]

        # Triple Bottom: 3 Lows (Troughs), 2 intervening Highs (Neckline Peaks)
        elif len(lows) >= 3 and len(highs) >= 2:
            p_lows = [
                PatternPoint(price=l.price, timestamp=l.timestamp, index=l.index, point_label="Low")
                for l in lows[-3:]
            ]
            p_highs = [
                PatternPoint(price=h.price, timestamp=h.timestamp, index=h.index, point_label="Neckline")
                for h in highs[-2:]
            ]

            slope_low, intercept_low, r2_low = fit_line(p_lows)
            slope_low_norm = normalize_slope(slope_low, atr)

            if is_horizontal(slope_low_norm, threshold=0.03):
                pattern_type = PatternType.TRIPLE_BOTTOM
                direction = PatternDirection.BULLISH
                p_points = p_highs + p_lows
                trendlines = [
                    Trendline(start_point=p_lows[0], end_point=p_lows[-1], slope=slope_low, intercept=intercept_low)
                ]

        if pattern_type is None:
            return None, None

        # Symmetry & scores
        left_width = abs(p_points[1].index - p_points[0].index)
        right_width = abs(p_points[2].index - p_points[1].index)
        symmetry = calculate_symmetry_score(left_width, right_width)

        min_p, max_p = get_extremes(swings_subset)
        height = max_p - min_p
        atr_norm = calculate_atr_normalization(height, atr)

        fit_score = calculate_fit_score(r2_high, r2_low)
        geom = calculate_geometry_score(fit_score)
        vol_score = 1.0

        overall = calculate_overall_score(geom, symmetry, fit_score, vol_score, atr_norm)

        meta = PatternMetadata(
            source_engine=self.detector_id,
            version="1.0.0",
            parameters={"left_width": left_width, "right_width": right_width},
            quality_score=overall,
            geometry_score=geom,
            symmetry_score=symmetry,
            touch_count=3,
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        candidate = PatternCandidate(
            candidate_id=f"cand-triple-{symbol}-{timeframe}-{p_points[-1].index}",
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
            # Breakout level is neckline price. For triple top: min of intervening lows. For triple bottom: max of intervening highs.
            intervening_prices = [p.price for p in p_points if p.point_label == "Neckline"]
            if intervening_prices:
                neckline_price = min(intervening_prices) if direction == PatternDirection.BEARISH else max(intervening_prices)
            else:
                neckline_price = p_points[-1].price

            is_bull_break, is_bear_break = evaluate_breakout(latest_swing.price, neckline_price, neckline_price)

            confirmed = False
            if direction == PatternDirection.BULLISH and is_bull_break:
                confirmed = True
            elif direction == PatternDirection.BEARISH and is_bear_break:
                confirmed = True

            if confirmed:
                match = PatternMatch(
                    match_id=f"match-triple-{symbol}-{timeframe}-{latest_swing.index}",
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
