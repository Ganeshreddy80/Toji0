"""Diamond Pattern Detector for identifying Diamond Top and Diamond Bottom reversal patterns."""

from __future__ import annotations

import logging
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
from price_action.utils.geometry import line_value
from price_action.utils.statistics import calculate_fit_score, normalize_slope
from price_action.utils.validation import validate_swing_counts
from price_action.utils.swing_selection import select_recent_swings, get_extremes
from price_action.utils.pattern_score import (
    calculate_geometry_score,
    calculate_symmetry_score,
    calculate_atr_normalization,
    calculate_overall_score,
)
from price_action.utils.breakout import evaluate_breakout
from toji_platform.core.dependency_injection.interfaces import IContainer

logger = logging.getLogger(__name__)


class DiamondDetector(IPatternDetector):
    """Detects Diamond Top and Diamond Bottom reversal chart patterns."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "diamond_detector"

    def detect(self, context: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        if not isinstance(context, DetectorContext):
            context = DetectorContext.from_market_state(context)

        symbol = context.market_state.symbol
        timeframe = context.timeframe
        swings = context.swings
        atr = context.atr

        if len(swings) < 6 or not validate_swing_counts(swings, min_highs=3, min_lows=3):
            return [], []

        recent_swings = sorted(swings[-8:], key=lambda s: s.index)
        candidates = []
        matches = []
        ts = getattr(context.market_state, "updated_at", datetime.now(timezone.utc))

        # Pass 1: Fit on recent_swings[:-1] to check breakout on the latest swing point
        if len(recent_swings) >= 7:
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
        highs = [s for s in swings_subset if s.point_type == SwingType.HIGH]
        lows = [s for s in swings_subset if s.point_type == SwingType.LOW]

        if len(highs) < 3 or len(lows) < 3:
            return None, None

        # Take last 3 highs and lows for the diamond structure
        h1, h2, h3 = highs[-3:]
        l1, l2, l3 = lows[-3:]

        # Validate order
        # We need h1, l1 to precede h2, l2, which precede h3, l3.
        # Since highs and lows lists are sorted by index, this is naturally true.
        
        # Broadening Phase: High2 > High1 and Low2 < Low1
        # Converging Phase: High3 < High2 and Low3 > Low2
        is_broadening = h2.price > h1.price and l2.price < l1.price
        is_converging = h3.price < h2.price and l3.price > l2.price

        if not (is_broadening and is_converging):
            return None, None

        # Preceding trend to classify Top vs Bottom candidates
        first_swing = swings_subset[0]
        mid_price_start = (h1.price + l1.price) / 2.0
        
        if first_swing.price < mid_price_start:
            pattern_type = PatternType.DIAMOND_TOP
            direction = PatternDirection.BEARISH
        else:
            pattern_type = PatternType.DIAMOND_BOTTOM
            direction = PatternDirection.BULLISH

        p_points = [
            PatternPoint(price=h1.price, timestamp=h1.timestamp, index=h1.index, point_label="High1"),
            PatternPoint(price=l1.price, timestamp=l1.timestamp, index=l1.index, point_label="Low1"),
            PatternPoint(price=h2.price, timestamp=h2.timestamp, index=h2.index, point_label="High2"),
            PatternPoint(price=l2.price, timestamp=l2.timestamp, index=l2.index, point_label="Low2"),
            PatternPoint(price=h3.price, timestamp=h3.timestamp, index=h3.index, point_label="High3"),
            PatternPoint(price=l3.price, timestamp=l3.timestamp, index=l3.index, point_label="Low3"),
        ]

        # Calculate slopes for converging right trendlines
        # Upper Right Trendline (High2 to High3)
        slope_ur = (h3.price - h2.price) / max(1, h3.index - h2.index)
        intercept_ur = h2.price - slope_ur * h2.index

        # Lower Right Trendline (Low2 to Low3)
        slope_lr = (l3.price - l2.price) / max(1, l3.index - l2.index)
        intercept_lr = l2.price - slope_lr * l2.index

        trendlines = [
            Trendline(start_point=p_points[2], end_point=p_points[4], slope=slope_ur, intercept=intercept_ur),
            Trendline(start_point=p_points[3], end_point=p_points[5], slope=slope_lr, intercept=intercept_lr),
        ]

        # Symmetry: compare broadening width to converging width
        broad_width = max(h2.index, l2.index) - min(h1.index, l1.index)
        conv_width = max(h3.index, l3.index) - min(h2.index, l2.index)
        symmetry = calculate_symmetry_score(broad_width, conv_width)

        min_p, max_p = get_extremes(swings_subset)
        height = max_p - min_p
        atr_norm = calculate_atr_normalization(height, atr)

        fit_score = 1.0
        geom = calculate_geometry_score(fit_score)
        vol_score = 1.0
        overall = calculate_overall_score(geom, symmetry, fit_score, vol_score, atr_norm)

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        meta = PatternMetadata(
            source_engine=self.detector_id,
            version="1.0.0",
            parameters={"broad_width": broad_width, "conv_width": conv_width},
            quality_score=overall,
            geometry_score=geom,
            symmetry_score=symmetry,
            touch_count=6,
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        candidate = PatternCandidate(
            candidate_id=f"cand-diamond-{symbol}-{timeframe}-{h3.index}",
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
            upper_val = line_value(slope_ur, intercept_ur, latest_swing.index)
            lower_val = line_value(slope_lr, intercept_lr, latest_swing.index)

            is_bullish_break, is_bearish_break = evaluate_breakout(latest_swing.price, upper_val, lower_val)

            # Diamond Top confirms on bearish breakout
            if pattern_type == PatternType.DIAMOND_TOP and is_bearish_break:
                match = PatternMatch(
                    match_id=f"match-diamond-{symbol}-{timeframe}-{latest_swing.index}",
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
            # Diamond Bottom confirms on bullish breakout
            elif pattern_type == PatternType.DIAMOND_BOTTOM and is_bullish_break:
                match = PatternMatch(
                    match_id=f"match-diamond-{symbol}-{timeframe}-{latest_swing.index}",
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
