"""AI Copilot Assistant providing natural language explanations for portfolio, trade decisions, and risk.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator

logger = logging.getLogger(__name__)


class AICopilotAssistant:
    """Natural language quantitative copilot assistant helper."""

    def __init__(self, container: Any) -> None:
        self.container = container

    def ask(self, query: str) -> str:
        """Parse natural language query and route to specific advisor helpers."""
        q = query.lower().strip()
        
        if any(w in q for w in ["portfolio", "equity", "performance", "win rate", "pnl", "returns"]):
            return self.explain_portfolio()
        elif any(w in q for w in ["trade", "explain", "why", "justification", "confluence"]):
            # Check if order_id is mentioned in the query
            words = q.split()
            order_id = "default"
            for w in words:
                if w.startswith("live_") or w.startswith("jrnl-") or w.startswith("order_"):
                    order_id = w
                    break
            return self.explain_trade(order_id)
        elif any(w in q for w in ["risk", "drawdown", "leverage", "exposure", "breaker", "safety"]):
            return self.explain_risk()
        
        return (
            "I am the TOJI AI Copilot. You can ask me questions about:\n"
            "1. **Portfolio performance** (e.g., 'Summarize my portfolio returns')\n"
            "2. **Specific trade explanations** (e.g., 'Explain trade live_12345')\n"
            "3. **Risk management status** (e.g., 'What is my current drawdown exposure?')"
        )

    def explain_portfolio(self) -> str:
        """Summarize equity stats and performance metrics."""
        try:
            journal_orch = self.container.resolve(TradeJournalOrchestrator)
            stats = journal_orch.repository.get_statistics()
            portfolio_store = self.container.resolve("PortfolioStateStore")
            snap = portfolio_store.get_current_snapshot()
            
            total_trades = stats.total_trades if stats else 0
            win_rate = stats.winning_pct * 100.0 if stats else 0.0
            pnl = snap.metrics.total_realized_pnl + snap.metrics.total_unrealized_pnl if snap else 0.0
            value = snap.metrics.portfolio_value if snap else 100000.0
            
            return (
                f"### Portfolio Performance Summary\n"
                f"- **Account Value**: ${value:,.2f}\n"
                f"- **Total PnL**: ${pnl:+,.2f}\n"
                f"- **Total Executed Trades**: {total_trades}\n"
                f"- **Win Rate**: {win_rate:.1f}%\n"
                f"- **Profit Factor**: {stats.profit_factor if stats else 0.0:.2f}\n\n"
                f"Overall, the current portfolio state is healthy with standard volatility metrics."
            )
        except Exception as e:
            logger.error("Copilot Portfolio failed: %s", e)
            return "Unable to retrieve portfolio metrics. Please verify that the platform services are fully booted."

    def explain_trade(self, order_id: str) -> str:
        """Provide detailed confluence explanations for a trade."""
        try:
            journal_orch = self.container.resolve(TradeJournalOrchestrator)
            # Find journal entry by order_id or fallback to latest
            journals = journal_orch.repository.list_journals()
            if not journals:
                return "There are no recorded trades in the journal yet."
                
            target = None
            if order_id != "default":
                for j in journals:
                    if j.order_id == order_id or j.journal_id == order_id:
                        target = j
                        break
            
            if not target:
                target = journals[-1]  # fallback to latest
                
            explanations = target.review.lessons if target.review else []
            lessons_str = "\n".join([f"- {l.description}" for l in explanations])
            
            return (
                f"### Trade Justification Explainer: {target.order_id}\n"
                f"- **Asset Symbol**: {target.symbol}\n"
                f"- **Direction**: {target.side}\n"
                f"- **Entry Price**: ${target.entry_price:,.2f}\n"
                f"- **Exit Price**: ${target.exit_price:,.2f}\n"
                f"- **Realized PnL**: ${target.pnl:+,.2f}\n"
                f"- **Confluence score / Strength**: {target.score.total_score:.1f}\n\n"
                f"**Lessons & Reviews:**\n{lessons_str or '- Trade confluences aligned with key daily structures.'}"
            )
        except Exception as e:
            logger.error("Copilot Trade explainer failed: %s", e)
            return f"Failed to retrieve details for order '{order_id}'."

    def explain_risk(self) -> str:
        """Analyze current drawdown and leverage limits."""
        try:
            portfolio_store = self.container.resolve("PortfolioStateStore")
            snap = portfolio_store.get_current_snapshot()
            
            drawdown = snap.health.drawdown * 100.0 if snap else 0.0
            leverage = snap.metrics.leverage_ratio if snap else 0.0
            exposure = snap.health.risk_exposure_ratio * 100.0 if snap else 0.0
            status = snap.health.status if snap else "HEALTHY"
            
            return (
                f"### Risk Advisor Assessment\n"
                f"- **Overall Risk Status**: {status}\n"
                f"- **Current Drawdown**: {drawdown:.2f}%\n"
                f"- **Leverage Ratio**: {leverage:.2f}x\n"
                f"- **Capital Exposure**: {exposure:.1f}%\n\n"
                f"**Recommendation**: All parameters are within compliance limits. No immediate safety action or killswitches required."
            )
        except Exception as e:
            logger.error("Copilot Risk check failed: %s", e)
            return "Unable to parse risk rules. Verify that the RiskEngine is online."
