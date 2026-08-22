"""Wedge Pattern Detector for identifying Rising Wedges and Falling Wedges."""

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
    Trendline,
)
from price_action.utils.regression import fit_line
from price_action.utils.geometry import line_value, check_convergence
from price_action.utils.statistics import calculate_fit_score, normalize_slope
from price_action.utils.projection import check_breakout
from price_action.utils.tolerance import is_falling, is_rising
from price_action.utils.validation import validate_swing_counts
from toji_platform.core.dependency_injection.interfaces import IContainer

logger = logging.getLogger(__name__)


class WedgeDetector(IPatternDetector):
    """Detects converging wedge chart patterns where both trendlines slope in the same direction."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "wedge_detector"

    def detect(self, context: DetectorContext | MarketState) -> tuple[list[PatternCandidate], list[PatternMatch]]:
        if not isinstance(context, DetectorContext):
            context = DetectorContext.from_market_state(context)

        symbol = context.market_state.symbol
        timeframe = context.timeframe
        swings = context.swings
        atr = context.atr

        if len(swings) < 4 or not validate_swing_counts(swings, min_highs=2, min_lows=2):
            return [], []

        recent_swings = sorted(swings[-6:], key=lambda s: s.index)
        candidates = []
        matches = []
        ts = getattr(context.market_state, "updated_at", datetime.now(timezone.utc))

        # Pass 1: Fit on recent_swings[:-1] to check breakout on the latest swing point
        if len(recent_swings) >= 5:
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

        # Rising Wedge: both slopes positive, lower line steeper (converges upward)
        if is_rising(slope_high_norm) and is_rising(slope_low_norm) and slope_low_norm > slope_high_norm:
            pattern_type = PatternType.RISING_WEDGE
            direction = PatternDirection.BEARISH  # Reversal bias
        # Falling Wedge: both slopes negative, upper line steeper (converges downward)
        elif is_falling(slope_high_norm) and is_falling(slope_low_norm) and slope_high_norm < slope_low_norm:
            pattern_type = PatternType.FALLING_WEDGE
            direction = PatternDirection.BULLISH  # Reversal bias

        if pattern_type is None:
            return None, None

        # Validate convergence
        first_idx = min(swings_subset[0].index, swings_subset[1].index)
        last_idx = max(swings_subset[-1].index, swings_subset[-2].index)

        if not check_convergence(
            slope_high, intercept_high, slope_low, intercept_low, first_idx, last_idx
        ):
            return None, None

        fit_score = calculate_fit_score(r2_high, r2_low)

        upper_trend = Trendline(
            start_point=p_highs[0], end_point=p_highs[-1], slope=slope_high, intercept=intercept_high
        )
        lower_trend = Trendline(
            start_point=p_lows[0], end_point=p_lows[-1], slope=slope_low, intercept=intercept_low
        )

        ts = timestamp or (latest_swing.timestamp if latest_swing else datetime.now(timezone.utc))

        candidate = PatternCandidate(
            candidate_id=f"cand-wedge-{symbol}-{timeframe}-{highs[-1].index}",
            symbol=symbol,
            timeframe=timeframe,
            pattern_type=pattern_type,
            direction=direction,
            points=p_highs + p_lows,
            trendlines=[upper_trend, lower_trend],
            score=fit_score,
            detected_at=ts,
        )

        match = None
        if latest_swing is not None:
            upper_val = line_value(slope_high, intercept_high, latest_swing.index)
            lower_val = line_value(slope_low, intercept_low, latest_swing.index)

            is_bullish_break, is_bearish_break = check_breakout(latest_swing.price, upper_val, lower_val)

            if direction == PatternDirection.BULLISH and is_bullish_break:
                match = PatternMatch(
                    match_id=f"match-wedge-{symbol}-{timeframe}-{latest_swing.index}",
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_type=pattern_type,
                    direction=direction,
                    status=PatternStatus.CONFIRMED,
                    points=p_highs + p_lows,
                    trendlines=[upper_trend, lower_trend],
                    fit_score=fit_score,
                    confirmed_at=ts,
                )
            elif direction == PatternDirection.BEARISH and is_bearish_break:
                match = PatternMatch(
                    match_id=f"match-wedge-{symbol}-{timeframe}-{latest_swing.index}",
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_type=pattern_type,
                    direction=direction,
                    status=PatternStatus.CONFIRMED,
                    points=p_highs + p_lows,
                    trendlines=[upper_trend, lower_trend],
                    fit_score=fit_score,
                    confirmed_at=ts,
                )

        return candidate, match
