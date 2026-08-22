"""Pluggable Pattern Engine coordinator for the Price Action Subsystem."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from market_intelligence.core.models import MarketState
from price_action.core.enums import PatternStatus
from price_action.core.exceptions import DetectorRegistrationError
from price_action.core.interfaces import IPatternDetector
from price_action.core.models import (
    PatternCandidate,
    PatternMatch,
    PatternState,
)
from toji_platform.core.dependency_injection.interfaces import IContainer

logger = logging.getLogger(__name__)


class PatternEngine:
    """Manages the registration and execution of chart pattern detectors."""

    def __init__(self, container: IContainer | None = None) -> None:
        self._container = container
        self._detectors: dict[str, IPatternDetector] = {}

        # Register default detectors
        from price_action.analysis.triangle_detector import TriangleDetector
        from price_action.analysis.flag_detector import FlagDetector
        from price_action.analysis.wedge_detector import WedgeDetector
        from price_action.analysis.channel_detector import ChannelDetector
        from price_action.analysis.double_pattern_detector import DoublePatternDetector
        from price_action.analysis.triple_pattern_detector import TriplePatternDetector
        from price_action.analysis.head_shoulders_detector import HeadShouldersDetector
        from price_action.analysis.pennant_detector import PennantDetector
        from price_action.analysis.rectangle_detector import RectangleDetector
        from price_action.analysis.cup_handle_detector import CupHandleDetector
        from price_action.analysis.broadening_detector import BroadeningDetector
        from price_action.analysis.diamond_detector import DiamondDetector
        from price_action.analysis.rounding_detector import RoundingDetector
        from price_action.analysis.harmonic_detector import HarmonicDetector

        self.register_detector(TriangleDetector(container))
        self.register_detector(FlagDetector(container))
        self.register_detector(WedgeDetector(container))
        self.register_detector(ChannelDetector(container))
        self.register_detector(DoublePatternDetector(container))
        self.register_detector(TriplePatternDetector(container))
        self.register_detector(HeadShouldersDetector(container))
        self.register_detector(PennantDetector(container))
        self.register_detector(RectangleDetector(container))
        self.register_detector(CupHandleDetector(container))
        self.register_detector(BroadeningDetector(container))
        self.register_detector(DiamondDetector(container))
        self.register_detector(RoundingDetector(container))
        self.register_detector(HarmonicDetector(container))

    def set_container(self, container: IContainer | None) -> None:
        """Set the dependency injection container and propagate to all detectors."""
        self._container = container
        for detector in self._detectors.values():
            if hasattr(detector, "_container"):
                detector._container = container

    def register_detector(self, detector: IPatternDetector) -> None:
        """Register a pluggable pattern detector."""
        detector_id = detector.detector_id
        if not detector_id:
            raise DetectorRegistrationError("Detector must have a valid detector_id.")

        if detector_id in self._detectors:
            raise DetectorRegistrationError(f"Detector '{detector_id}' is already registered.")

        self._detectors[detector_id] = detector
        logger.info("PatternEngine: Registered detector '%s'", detector_id)

    def remove_detector(self, detector_id: str) -> None:
        """Remove a registered pattern detector by ID."""
        if detector_id not in self._detectors:
            raise DetectorRegistrationError(f"Detector '{detector_id}' is not registered.")

        self._detectors.pop(detector_id)
        logger.info("PatternEngine: Removed detector '%s'", detector_id)

    def run(self, market_state: MarketState) -> PatternState:
        """Execute all registered pattern detectors and aggregate their states."""
        symbol = market_state.symbol
        timeframe = market_state.timeframe

        from price_action.core.models import DetectorContext
        context = DetectorContext.from_market_state(market_state)

        all_candidates: list[PatternCandidate] = []
        all_matches: list[PatternMatch] = []

        # Execute each detector sequentially (dispatch)
        for detector_id, detector in self._detectors.items():
            try:
                candidates, matches = detector.detect(context)
                all_candidates.extend(candidates)
                all_matches.extend(matches)
            except Exception as e:
                logger.error("PatternEngine: Pluggable detector '%s' failed: %s", detector_id, e)

        # Categorize matches based on lifecycle status
        active_patterns = [
            m for m in all_matches
            if m.status in (PatternStatus.CONFIRMED, PatternStatus.DEVELOPING)
        ]
        historical_patterns = [
            m for m in all_matches
            if m.status in (PatternStatus.INVALIDATED, PatternStatus.COMPLETED)
        ]

        # Use updated_at from market_state if available, else default to current UTC time
        updated_at = getattr(market_state, "updated_at", datetime.now(timezone.utc))

        return PatternState(
            symbol=symbol,
            timeframe=timeframe,
            active_patterns=active_patterns,
            candidate_patterns=all_candidates,
            historical_patterns=historical_patterns,
            updated_at=updated_at,
        )
