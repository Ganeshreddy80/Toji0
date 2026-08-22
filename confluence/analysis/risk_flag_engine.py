"""Risk Flag Engine for evaluating 7 types of market risk conditions."""

from __future__ import annotations

from datetime import datetime, timezone

from market_intelligence.core.models import MarketState
from confluence.core.enums import RiskFlagType
from confluence.core.models import ConfluenceScore, RiskFlag


class RiskFlagEngine:
    """Rules-based engine that evaluates market conditions against risk thresholds.

    Evaluates 7 risk flag types:
        1. Low Liquidity: liquidity score < 40 or volume score < 30
        2. High Volatility: volatility percentile > 90 or ATR spike
        3. Correlation Risk: |max correlation| > 0.85
        4. Weekend Risk: UTC Saturday or Sunday
        5. Funding Risk: stub for spot (always inactive)
        6. News/Event Risk: framework stub (always inactive)
        7. Spread Risk: bid-ask spread > threshold
    """

    def __init__(
        self,
        liquidity_threshold: float = 40.0,
        volume_threshold: float = 30.0,
        volatility_percentile_threshold: float = 90.0,
        correlation_threshold: float = 0.85,
        spread_threshold: float = 0.5,
    ) -> None:
        self._liquidity_threshold = liquidity_threshold
        self._volume_threshold = volume_threshold
        self._volatility_percentile_threshold = volatility_percentile_threshold
        self._correlation_threshold = correlation_threshold
        self._spread_threshold = spread_threshold

    def evaluate(
        self,
        market_state: MarketState,
        confluence_score: ConfluenceScore,
        evaluation_time: datetime | None = None,
    ) -> list[RiskFlag]:
        """Evaluate all risk flags against current market conditions."""
        now = evaluation_time or datetime.now(timezone.utc)
        flags: list[RiskFlag] = []

        flags.append(self._check_low_liquidity(confluence_score, market_state))
        flags.append(self._check_high_volatility(market_state))
        flags.append(self._check_correlation_risk(market_state))
        flags.append(self._check_weekend_risk(now))
        flags.append(self._check_funding_risk())
        flags.append(self._check_news_event_risk())
        flags.append(self._check_spread_risk(market_state))

        return flags

    def _check_low_liquidity(
        self,
        score: ConfluenceScore,
        market_state: MarketState,
    ) -> RiskFlag:
        """Low liquidity: confluence liquidity score or volume score below threshold."""
        liq_low = score.liquidity_score < self._liquidity_threshold
        vol_low = score.volume_score < self._volume_threshold
        active = liq_low or vol_low

        severity = 0.0
        if active:
            severity = 0.7
            if liq_low and vol_low:
                severity = 0.9

        desc = "Liquidity and volume conditions are adequate."
        if active:
            parts = []
            if liq_low:
                parts.append(f"liquidity score {score.liquidity_score:.1f} < {self._liquidity_threshold}")
            if vol_low:
                parts.append(f"volume score {score.volume_score:.1f} < {self._volume_threshold}")
            desc = f"Low liquidity detected: {'; '.join(parts)}."

        return RiskFlag(
            flag_type=RiskFlagType.LOW_LIQUIDITY,
            severity=round(severity, 2),
            description=desc,
            active=active,
        )

    def _check_high_volatility(self, market_state: MarketState) -> RiskFlag:
        """High volatility: volatility percentile above threshold."""
        active = False
        severity = 0.0
        desc = "Volatility within normal range."

        if market_state.volatility_analysis is not None:
            pct = market_state.volatility_analysis.volatility_percentile
            if pct > self._volatility_percentile_threshold:
                active = True
                severity = min(1.0, 0.6 + (pct - self._volatility_percentile_threshold) / 20.0)
                desc = f"Elevated volatility detected: percentile {pct:.1f}% > {self._volatility_percentile_threshold}%."

        return RiskFlag(
            flag_type=RiskFlagType.HIGH_VOLATILITY,
            severity=round(severity, 2),
            description=desc,
            active=active,
        )

    def _check_correlation_risk(self, market_state: MarketState) -> RiskFlag:
        """Correlation risk: any asset correlation above threshold."""
        active = False
        severity = 0.0
        desc = "Cross-asset correlations within acceptable range."

        if market_state.correlation_analysis is not None:
            correlations = market_state.correlation_analysis.correlations
            if correlations:
                max_corr = max(abs(v) for v in correlations.values()) if correlations else 0.0
                if max_corr > self._correlation_threshold:
                    active = True
                    severity = min(1.0, 0.5 + (max_corr - self._correlation_threshold) * 3.0)
                    desc = f"High cross-asset correlation detected: |max| = {max_corr:.2f} > {self._correlation_threshold}."

        return RiskFlag(
            flag_type=RiskFlagType.CORRELATION_RISK,
            severity=round(severity, 2),
            description=desc,
            active=active,
        )

    def _check_weekend_risk(self, now: datetime) -> RiskFlag:
        """Weekend risk: UTC Saturday (5) or Sunday (6)."""
        is_weekend = now.weekday() in (5, 6)
        severity = 0.4 if is_weekend else 0.0
        desc = "Weekend: reduced institutional participation and liquidity." if is_weekend else "Market in regular session."

        return RiskFlag(
            flag_type=RiskFlagType.WEEKEND_RISK,
            severity=severity,
            description=desc,
            active=is_weekend,
        )

    def _check_funding_risk(self) -> RiskFlag:
        """Funding risk: framework stub for spot markets (always inactive)."""
        return RiskFlag(
            flag_type=RiskFlagType.FUNDING_RISK,
            severity=0.0,
            description="Funding risk not applicable for spot markets.",
            active=False,
        )

    def _check_news_event_risk(self) -> RiskFlag:
        """News/Event risk: framework stub (requires external data feed)."""
        return RiskFlag(
            flag_type=RiskFlagType.NEWS_EVENT_RISK,
            severity=0.0,
            description="No scheduled high-impact events detected (external feed not connected).",
            active=False,
        )

    def _check_spread_risk(self, market_state: MarketState) -> RiskFlag:
        """Spread risk: bid-ask spread above threshold."""
        active = False
        severity = 0.0
        desc = "Spread within acceptable range."

        if market_state.liquidity_analysis is not None:
            spread = market_state.liquidity_analysis.bid_ask_spread
            if spread > self._spread_threshold:
                active = True
                severity = min(1.0, 0.5 + (spread - self._spread_threshold) * 2.0)
                desc = f"Wide spread detected: {spread:.4f} > {self._spread_threshold}."

        return RiskFlag(
            flag_type=RiskFlagType.SPREAD_RISK,
            severity=round(severity, 2),
            description=desc,
            active=active,
        )
