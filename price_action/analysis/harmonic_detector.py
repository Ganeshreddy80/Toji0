"""Harmonic Pattern Foundation Detector for extracting legs and validating Fibonacci ratios."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from dataclasses import dataclass

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
from price_action.utils.fibonacci import calculate_ratio, validate_ratio
from price_action.utils.statistics import calculate_fit_score
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


@dataclass(frozen=True)
class HarmonicLegs:
    """Structure holding the swing points of a 5-point harmonic pattern leg structure."""

    x: SwingPoint
    a: SwingPoint
    b: SwingPoint
    c: SwingPoint
    d: SwingPoint

    @property
    def xa_height(self) -> float:
        return abs(self.a.price - self.x.price)

    @property
    def ab_height(self) -> float:
        return abs(self.b.price - self.a.price)

    @property
    def bc_height(self) -> float:
        return abs(self.c.price - self.b.price)

    @property
    def cd_height(self) -> float:
        return abs(self.d.price - self.c.price)

    @property
    def ab_xa_ratio(self) -> float:
        return calculate_ratio(self.ab_height, self.xa_height)

    @property
    def bc_ab_ratio(self) -> float:
        return calculate_ratio(self.bc_height, self.ab_height)

    @property
    def cd_bc_ratio(self) -> float:
        return calculate_ratio(self.cd_height, self.bc_height)


class HarmonicValidator:
    """Validates harmonic leg ratios against target levels with tolerance."""

    @staticmethod
    def validate_structure(
        legs: HarmonicLegs,
        ab_xa_targets: list[float],
        bc_ab_targets: list[float],
        cd_bc_targets: list[float],
        tolerance: float = 0.05,
    ) -> bool:
        """Check if harmonic legs match any of the targets within tolerance."""
        ab_xa_ok = any(validate_ratio(legs.ab_xa_ratio, t, tolerance) for t in ab_xa_targets)
        bc_ab_ok = any(validate_ratio(legs.bc_ab_ratio, t, tolerance) for t in bc_ab_targets)
        cd_bc_ok = any(validate_ratio(legs.cd_bc_ratio, t, tolerance) for t in cd_bc_targets)
        return ab_xa_ok and bc_ab_ok and cd_bc_ok


class HarmonicDetector(IPatternDetector):
    """Detects harmonic patterns using the leg extraction and validation foundation."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container

    @property
    def detector_id(self) -> str:
        return "harmonic_detector"

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
        if len(swings_subset) < 5:
            return None, None

        # Take the last 5 swings to construct the legs (X, A, B, C, D)
        x, a, b, c, d = swings_subset[-5:]

        # Alternate verification: High, Low, High, Low, High or Low, High, Low, High, Low
        valid_alternating = (
            (x.point_type == SwingType.HIGH and a.point_type == SwingType.LOW and
             b.point_type == SwingType.HIGH and c.point_type == SwingType.LOW and
             d.point_type == SwingType.HIGH) or
            (x.point_type == SwingType.LOW and a.point_type == SwingType.HIGH and
             b.point_type == SwingType.LOW and c.point_type == SwingType.HIGH and
             d.point_type == SwingType.LOW)
        )

        if not valid_alternating:
            return None, None

        legs = HarmonicLegs(x, a, b, c, d)

        # Validate a general harmonic range (Gartley/Bat/etc. foundation check)
        # Typically:
        # AB/XA: [0.382, 0.886]
        # BC/AB: [0.382, 0.886]
        # CD/BC: [1.13, 3.618]
        is_harmonic = (
            0.3 <= legs.ab_xa_ratio <= 1.0 and
            0.3 <= legs.bc_ab_ratio <= 1.0 and
            1.0 <= legs.cd_bc_ratio <= 4.0
        )

        if not is_harmonic:
            return None, None

        # Direction is bullish if D is a Low (potential reversal to the upside)
        # Direction is bearish if D is a High (potential reversal to the downside)
        direction = PatternDirection.BULLISH if d.point_type == SwingType.LOW else PatternDirection.BEARISH

        p_points = [
            PatternPoint(price=x.price, timestamp=x.timestamp, index=x.index, point_label="X"),
            PatternPoint(price=a.price, timestamp=a.timestamp, index=a.index, point_label="A"),
            PatternPoint(price=b.price, timestamp=b.timestamp, index=b.index, point_label="B"),
            PatternPoint(price=c.price, timestamp=c.timestamp, index=c.index, point_label="C"),
            PatternPoint(price=d.price, timestamp=d.timestamp, index=d.index, point_label="D"),
        ]

        # Trendline representation (XA and CD legs)
        trendlines = [
            Trendline(start_point=p_points[0], end_point=p_points[1], slope=(a.price - x.price)/(a.index - x.index), intercept=x.price - ((a.price - x.price)/(a.index - x.index))*x.index),
            Trendline(start_point=p_points[3], end_point=p_points[4], slope=(d.price - c.price)/(d.index - c.index), intercept=c.price - ((d.price - c.price)/(d.index - c.index))*c.index),
        ]

        # Symmetry: compare XAB duration to BCD duration
        left_width = abs(b.index - x.index)
        right_width = abs(d.index - b.index)
        symmetry = calculate_symmetry_score(left_width, right_width)

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
            parameters={
                "ab_xa_ratio": legs.ab_xa_ratio,
                "bc_ab_ratio": legs.bc_ab_ratio,
                "cd_bc_ratio": legs.cd_bc_ratio,
            },
            quality_score=overall,
            geometry_score=geom,
            symmetry_score=symmetry,
            touch_count=5,
            regression_fit=fit_score,
            volume_confirmation=vol_score,
            atr_normalization=atr_norm,
        )

        candidate = PatternCandidate(
            candidate_id=f"cand-harmonic-{symbol}-{timeframe}-{d.index}",
            symbol=symbol,
            timeframe=timeframe,
            pattern_type=PatternType.HARMONIC,
            direction=direction,
            points=p_points,
            trendlines=trendlines,
            score=overall,
            detected_at=ts,
            metadata=meta,
        )

        match = None
        if latest_swing is not None:
            # Reversal confirms immediately when point D completes (candidate is confirmed as match)
            # Or if there is a breakout beyond D's price
            is_bullish_break, is_bearish_break = evaluate_breakout(latest_swing.price, d.price, d.price)

            confirmed = False
            if direction == PatternDirection.BULLISH and latest_swing.price > d.price:
                confirmed = True
            elif direction == PatternDirection.BEARISH and latest_swing.price < d.price:
                confirmed = True

            if confirmed:
                match = PatternMatch(
                    match_id=f"match-harmonic-{symbol}-{timeframe}-{latest_swing.index}",
                    symbol=symbol,
                    timeframe=timeframe,
                    pattern_type=PatternType.HARMONIC,
                    direction=direction,
                    status=PatternStatus.CONFIRMED,
                    points=p_points,
                    trendlines=trendlines,
                    fit_score=overall,
                    confirmed_at=ts,
                    metadata=meta,
                )

        return candidate, match
