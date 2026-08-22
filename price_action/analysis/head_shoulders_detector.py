"""Head & Shoulders and Inverse Head & Shoulders Pattern Detector."""

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


class HeadShouldersDetector(IPatternDetector):
    """Detects Head & Shoulders and Inverse Head & Shoulders reversal chart patterns."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "head_shoulders_detector"

    def detect(self, context: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        if not isinstance(context, DetectorContext):
            context = DetectorContext.from_market_state(context)

        symbol = context.market_state.symbol
        timeframe = context.timeframe
        swings = context.swings
        atr = context.atr

        # H&S needs at least 5 swing points
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
        r2_neck = 1.0
        slope_neck, intercept_neck = 0.0, 0.0

        # Head & Shoulders: 3 Highs (Left Shoulder, Head, Right Shoulder), 2 Lows (Neckline)
        if len(highs) >= 3 and len(lows) >= 2:
            p_highs = [
                PatternPoint(price=h.price, timestamp=h.timestamp, index=h.index, point_label=lbl)
                for h, lbl in zip(highs[-3:], ["LeftShoulder", "Head", "RightShoulder"])
            ]
            p_lows = [
                PatternPoint(price=l.price, timestamp=l.timestamp, index=l.index, point_label="Neckline")
                for l in lows[-2:]
            ]

            # Validate H&S geometry: Left Shoulder < Head > Right Shoulder
            if p_highs[1].price > p_highs[0].price and p_highs[1].price > p_highs[2].price:
                pattern_type = PatternType.HEAD_AND_SHOULDERS
                direction = PatternDirection.BEARISH
                p_points = p_highs + p_lows

                # Fit neckline
                slope_neck, intercept_neck, r2_neck = fit_line(p_lows)
                trendlines = [
                    Trendline(start_point=p_lows[0], end_point=p_lows[1], slope=slope_neck, intercept=intercept_neck)
                ]

        # Inverse Head & Shoulders: 3 Lows (Left Shoulder, Head, Right Shoulder), 2 Highs (Neckline)
        elif len(lows) >= 3 and len(highs) >= 2:
            p_lows = [
                PatternPoint(price=l.price, timestamp=l.timestamp, index=l.index, point_label=lbl)
                for l, lbl in zip(lows[-3:], ["LeftShoulder", "Head", "RightShoulder"])
            ]
            p_highs = [
                PatternPoint(price=h.price, timestamp=h.timestamp, index=h.index, point_label="Neckline")
                for h in highs[-2:]
            ]

            # Validate Inverse H&S geometry: Left Shoulder > Head < Right Shoulder
            if p_lows[1].price < p_lows[0].price and p_lows[1].price < p_lows[2].price:
                pattern_type = PatternType.INVERSE_HEAD_AND_SHOULDERS
                direction = PatternDirection.BULLISH
                p_points = p_lows + p_highs

                # Fit neckline
                slope_neck, intercept_neck, r2_neck = fit_line(p_highs)
                trendlines = [
                    Trendline(start_point=p_highs[0], end_point=p_highs[1], slope=slope_neck, intercept=intercept_neck)
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

        fit_score = calculate_fit_score(r2_neck, r2_neck)
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
            touch_count=5,
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        candidate = PatternCandidate(
            candidate_id=f"cand-hs-{symbol}-{timeframe}-{p_points[-1].index}",
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
            # Neckline value at latest_swing index
            neckline_val = line_value(slope_neck, intercept_neck, latest_swing.index)

            is_bull_break, is_bear_break = evaluate_breakout(latest_swing.price, neckline_val, neckline_val)

            confirmed = False
            if direction == PatternDirection.BULLISH and is_bull_break:
                confirmed = True
            elif direction == PatternDirection.BEARISH and is_bear_break:
                confirmed = True

            if confirmed:
                match = PatternMatch(
                    match_id=f"match-hs-{symbol}-{timeframe}-{latest_swing.index}",
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
