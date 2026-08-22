"""Reports generator for compiling market intelligence summaries."""

from __future__ import annotations

from typing import Any
from intelligence.models import MarketPulse, Opportunity


class IntelligenceReportGenerator:
    """Compiles structured reports summarizing market pulse, regimes, opportunities, and timing signals."""

    def generate_market_intelligence_report(self, pulses: dict[str, MarketPulse]) -> dict[str, Any]:
        """Compile a report summarizing overall market health pulse across multiple symbols.

        Args:
            pulses: Dict of symbol -> MarketPulse object.

        Returns:
            Report dictionary.
        """
        if not pulses:
            return {"summary": "No data available", "average_overall_score": 0.0}

        avg_health = sum(p.overall_score for p in pulses.values()) / len(pulses)
        avg_risk = sum(p.risk for p in pulses.values()) / len(pulses)
        avg_volatility = sum(p.volatility for p in pulses.values()) / len(pulses)
        avg_fear = sum(p.fear for p in pulses.values()) / len(pulses)

        symbols_by_health = sorted(pulses.keys(), key=lambda x: pulses[x].overall_score, reverse=True)

        return {
            "summary": "Market Intelligence Overview",
            "average_overall_score": avg_health,
            "average_risk_score": avg_risk,
            "average_volatility": avg_volatility,
            "average_fear_index": avg_fear,
            "total_assets_tracked": len(pulses),
            "healthiest_assets": symbols_by_health[:3],
            "highest_risk_assets": sorted(pulses.keys(), key=lambda x: pulses[x].risk, reverse=True)[:3],
        }

    def generate_opportunity_report(self, opportunities: list[Opportunity]) -> dict[str, Any]:
        """Compile a report of ranked trading opportunities.

        Args:
            opportunities: List of Opportunity objects.

        Returns:
            Report dictionary.
        """
        if not opportunities:
            return {"summary": "No opportunities identified", "opportunities": []}

        # Count by risk grade
        risk_counts: dict[str, int] = {}
        for opp in opportunities:
            grade_name = opp.risk_grade.value
            risk_counts[grade_name] = risk_counts.get(grade_name, 0) + 1

        return {
            "summary": "Ranked Market Opportunities",
            "total_opportunities": len(opportunities),
            "top_opportunity": opportunities[0].model_dump() if opportunities else None,
            "risk_grade_distribution": risk_counts,
            "opportunities": [opp.model_dump() for opp in opportunities],
        }

    def generate_regime_report(self, regimes: dict[str, str]) -> dict[str, Any]:
        """Compile a report detailing detected market regime phases across assets.

        Args:
            regimes: Dict of symbol -> regime phase name.

        Returns:
            Report dictionary.
        """
        if not regimes:
            return {"summary": "No regime data available", "distribution": {}}

        counts: dict[str, int] = {}
        for phase in regimes.values():
            counts[phase] = counts.get(phase, 0) + 1

        # Calculate percentages
        total = len(regimes)
        distribution_pct = {k: v / total for k, v in counts.items()}

        return {
            "summary": "Market Regime Distribution",
            "total_assets_analyzed": total,
            "phase_counts": counts,
            "phase_distribution_pct": distribution_pct,
            "assets_by_phase": {
                phase: [sym for sym, p in regimes.items() if p == phase]
                for phase in counts
            },
        }

    def generate_timing_report(
        self, decays: dict[str, float], sessions: dict[str, str]
    ) -> dict[str, Any]:
        """Compile a report summarizing signal aging and active market sessions.

        Args:
            decays: Dict of symbol -> signal decay factor (0.0 to 1.0).
            sessions: Dict of symbol -> active market session.

        Returns:
            Report dictionary.
        """
        if not decays:
            return {"summary": "No timing data available", "average_freshness": 0.0}

        avg_freshness = sum(decays.values()) / len(decays)

        # Count active sessions
        session_counts: dict[str, int] = {}
        for s in sessions.values():
            session_counts[s] = session_counts.get(s, 0) + 1

        return {
            "summary": "Signal Timing & Freshness Report",
            "average_freshness": avg_freshness,
            "active_session_counts": session_counts,
            "stale_signals_count": sum(1 for d in decays.values() if d < 0.5),
            "fresh_signals_count": sum(1 for d in decays.values() if d >= 0.8),
        }

    def generate_execution_window_report(self, windows: dict[str, str]) -> dict[str, Any]:
        """Compile a report detailing execution window states across assets.

        Args:
            windows: Dict of symbol -> execution window state (e.g. 'Immediate', 'Delayed').

        Returns:
            Report dictionary.
        """
        if not windows:
            return {"summary": "No execution window data available", "states": {}}

        counts: dict[str, int] = {}
        for state in windows.values():
            counts[state] = counts.get(state, 0) + 1

        return {
            "summary": "Execution Window Readiness Report",
            "total_assets": len(windows),
            "state_counts": counts,
            "immediate_execution_assets": [sym for sym, w in windows.items() if w == "Immediate"],
            "blocked_execution_assets": [sym for sym, w in windows.items() if w == "Blocked"],
        }
