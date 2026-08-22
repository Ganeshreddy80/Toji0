"""Rounding Pattern Detector for identifying Rounded Bottom and Rounded Top reversal patterns."""

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
from price_action.utils.regression import fit_quadratic
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


class RoundingDetector(IPatternDetector):
    """Detects Rounded Bottom and Rounded Top reversal chart patterns using quadratic fitting."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "rounding_detector"

    def detect(self, context: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        if not isinstance(context, DetectorContext):
            context = DetectorContext.from_market_state(context)

        symbol = context.market_state.symbol
        timeframe = context.timeframe
        swings = context.swings
        atr = context.atr

        if len(swings) < 5:
            return [], []

        recent_swings = sorted(swings[-6:], key=lambda s: s.index)
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
        p_points = [
            PatternPoint(price=s.price, timestamp=s.timestamp, index=s.index, point_label=s.point_type.value)
            for s in swings_subset
        ]

        a, b, c, r2 = fit_quadratic(p_points)

        # We require a good quadratic fit (R^2 >= 0.6)
        if r2 < 0.6:
            return None, None

        # Check curvature
        # a > 0 means U-shape (Rounded Bottom)
        # a < 0 means inverted U-shape (Rounded Top)
        if a > 1e-9:
            pattern_type = PatternType.ROUNDED_BOTTOM
            direction = PatternDirection.BULLISH
        elif a < -1e-9:
            pattern_type = PatternType.ROUNDED_TOP
            direction = PatternDirection.BEARISH
        else:
            return None, None

        # Trendline: construct a flat line at the breakout/lip level
        if pattern_type == PatternType.ROUNDED_BOTTOM:
            breakout_level = max(p_points[0].price, p_points[-1].price)
        else:
            breakout_level = min(p_points[0].price, p_points[-1].price)

        trendlines = [
            Trendline(
                start_point=p_points[0],
                end_point=p_points[-1],
                slope=0.0,
                intercept=breakout_level,
            )
        ]

        # Symmetry: compare first half duration to second half duration
        half_idx = len(p_points) // 2
        left_width = abs(p_points[half_idx].index - p_points[0].index)
        right_width = abs(p_points[-1].index - p_points[half_idx].index)
        symmetry = calculate_symmetry_score(left_width, right_width)

        min_p, max_p = get_extremes(swings_subset)
        height = max_p - min_p
        atr_norm = calculate_atr_normalization(height, atr)

        fit_score = max(0.0, min(1.0, r2))
        geom = calculate_geometry_score(fit_score)
        vol_score = 1.0
        overall = calculate_overall_score(geom, symmetry, fit_score, vol_score, atr_norm)

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        meta = PatternMetadata(
            source_engine=self.detector_id,
            version="1.0.0",
            parameters={"a": a, "b": b, "c": c},
            quality_score=overall,
            geometry_score=geom,
            symmetry_score=symmetry,
            touch_count=len(p_points),
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        candidate = PatternCandidate(
            candidate_id=f"cand-rounding-{symbol}-{timeframe}-{p_points[-1].index}",
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
            # Bullish breakout for Rounded Bottom, Bearish breakout for Rounded Top
            is_bullish_break, is_bearish_break = evaluate_breakout(latest_swing.price, breakout_level, breakout_level)

            if pattern_type == PatternType.ROUNDED_BOTTOM and is_bullish_break:
                match = PatternMatch(
                    match_id=f"match-rounding-{symbol}-{timeframe}-{latest_swing.index}",
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
            elif pattern_type == PatternType.ROUNDED_TOP and is_bearish_break:
                match = PatternMatch(
                    match_id=f"match-rounding-{symbol}-{timeframe}-{latest_swing.index}",
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
