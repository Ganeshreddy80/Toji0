"""Market Anomaly Detector — identifies flash crashes, volume spikes, spread explosions,
manipulation wicks, and liquidity vanishing events.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from research_platform.risk_governance.models import AnomalyEvent, TriggerReason

logger = logging.getLogger(__name__)


class MarketAnomalyDetector:
    """Scans tick-by-tick market data for anomalous conditions.

    Detection rules:
        Flash Crash:            Price falls > flash_crash_pct in a single bar.
        Volume Spike:           Volume > volume_spike_multiplier × avg_volume.
        Spread Explosion:       bid/ask spread > spread_explosion_bps bps.
        Manipulation Wick:      (high-low) / close  >  wick_pct with no directional follow.
        Liquidity Vanish:       market_volume drops to < liquidity_vanish_pct of baseline.
    """

    def __init__(
        self,
        flash_crash_pct: float = 5.0,
        volume_spike_multiplier: float = 5.0,
        spread_explosion_bps: float = 100.0,   # 1 %
        wick_pct: float = 3.0,
        liquidity_vanish_pct: float = 10.0,    # less than 10 % of baseline volume
    ) -> None:
        self.flash_crash_pct = flash_crash_pct
        self.volume_spike_multiplier = volume_spike_multiplier
        self.spread_explosion_bps = spread_explosion_bps
        self.wick_pct = wick_pct
        self.liquidity_vanish_pct = liquidity_vanish_pct

    def detect(
        self,
        symbol: str,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        prev_close: float,
        avg_volume: float,
        bid: float,
        ask: float,
        baseline_volume: float = 0.0,
    ) -> List[AnomalyEvent]:
        """Run all anomaly checks on a single bar.  Returns a (possibly empty) list."""
        events: List[AnomalyEvent] = []

        # 1. Flash crash: price dropped > flash_crash_pct vs prev bar close
        if prev_close > 0.0:
            drop_pct = (prev_close - close) / prev_close * 100.0
            if drop_pct >= self.flash_crash_pct:
                events.append(AnomalyEvent(
                    anomaly_type="FLASH_CRASH",
                    symbol=symbol,
                    detail=f"Price dropped {drop_pct:.2f}% in one bar (prev {prev_close:.2f} → {close:.2f})",
                    severity="CRITICAL",
                ))
                logger.critical("[ANOMALY] %s FLASH CRASH %.2f%%", symbol, drop_pct)

        # 2. Volume spike
        if avg_volume > 0.0 and volume > self.volume_spike_multiplier * avg_volume:
            multiple = volume / avg_volume
            events.append(AnomalyEvent(
                anomaly_type="VOLUME_SPIKE",
                symbol=symbol,
                detail=f"Volume {volume:.2f} = {multiple:.1f}× avg {avg_volume:.2f}",
                severity="HIGH",
            ))

        # 3. Spread explosion
        if bid > 0.0 and ask > 0.0:
            spread_bps = (ask - bid) / bid * 10_000.0
            if spread_bps >= self.spread_explosion_bps:
                events.append(AnomalyEvent(
                    anomaly_type="SPREAD_EXPLOSION",
                    symbol=symbol,
                    detail=f"Spread {spread_bps:.1f} bps (bid {bid:.2f} / ask {ask:.2f})",
                    severity="HIGH",
                ))

        # 4. Manipulation wick
        if close > 0.0:
            wick_range_pct = (high - low) / close * 100.0
            body_pct = abs(close - open_) / close * 100.0
            # Big range + tiny body = potential manipulation
            if wick_range_pct >= self.wick_pct and body_pct < wick_range_pct * 0.25:
                events.append(AnomalyEvent(
                    anomaly_type="MANIPULATION_WICK",
                    symbol=symbol,
                    detail=f"Wick range {wick_range_pct:.2f}%, body only {body_pct:.2f}%",
                    severity="MEDIUM",
                ))

        # 5. Liquidity vanish
        if baseline_volume > 0.0:
            vol_ratio_pct = volume / baseline_volume * 100.0
            if vol_ratio_pct < self.liquidity_vanish_pct:
                events.append(AnomalyEvent(
                    anomaly_type="LIQUIDITY_VANISH",
                    symbol=symbol,
                    detail=f"Volume {volume:.2f} = {vol_ratio_pct:.1f}% of baseline {baseline_volume:.2f}",
                    severity="MEDIUM",
                ))

        return events

    def has_critical(self, events: List[AnomalyEvent]) -> bool:
        """Returns True if any detected anomaly is CRITICAL (pause trading immediately)."""
        return any(e.severity == "CRITICAL" for e in events)
