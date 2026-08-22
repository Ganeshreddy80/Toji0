"""Daily, Weekly, and Monthly performance report generators and exporters.
"""

from __future__ import annotations

import os
import json
import csv
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from research_platform.trade_journal.orchestrator import TradeJournalOrchestrator
from research_platform.trade_journal.models import TradeJournal

logger = logging.getLogger(__name__)


class PerformanceReporter:
    """Generates daily, weekly, monthly performance reports and handles exports to markdown, JSON, and CSV."""

    def __init__(self, container: Any, reports_dir: str = "data/reports") -> None:
        self.container = container
        self.reports_dir = reports_dir
        os.makedirs(reports_dir, exist_ok=True)

    def generate_report(self, report_type: str = "daily", target_date: Optional[datetime] = None) -> Dict[str, Any]:
        """Compile trade metrics and export report contents to files."""
        if target_date is None:
            target_date = datetime.now(timezone.utc)

        # Resolve trades
        try:
            journal_orch = self.container.resolve(TradeJournalOrchestrator)
            all_trades = journal_orch.repository.list_journals()
        except Exception as e:
            logger.error("Reporter failed to resolve TradeJournalOrchestrator: %s", e)
            all_trades = []

        # Filter trades based on report window
        filtered_trades = self._filter_trades(all_trades, report_type, target_date)
        
        # Calculate stats
        total_pnl = sum(t.pnl for t in filtered_trades)
        wins = sum(1 for t in filtered_trades if t.pnl > 0)
        total_trades = len(filtered_trades)
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        
        report_id = f"rpt_{report_type}_{target_date.strftime('%Y%m%d')}"
        
        summary = {
            "report_id": report_id,
            "report_type": report_type.upper(),
            "target_date": target_date.strftime("%Y-%m-%d"),
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        # Generate markdown report
        markdown_content = self._build_markdown(summary, filtered_trades)
        
        # Save files
        self._write_files(report_id, summary, markdown_content, filtered_trades)
        
        return summary

    def _filter_trades(self, trades: List[TradeJournal], report_type: str, target_date: datetime) -> List[TradeJournal]:
        filtered = []
        now = target_date
        
        if report_type == "daily":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif report_type == "weekly":
            # Monday to Sunday of the target date week
            start_time = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = (start_time + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif report_type == "monthly":
            # Start and end of the current month
            start_time = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            next_month = (start_time + timedelta(days=32)).replace(day=1)
            end_time = (next_month - timedelta(seconds=1))
        else:
            # Fallback daily
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Standardize timezone to UTC
        start_time = start_time.replace(tzinfo=timezone.utc)
        end_time = end_time.replace(tzinfo=timezone.utc)

        for t in trades:
            t_time = t.exit_time
            if t_time.tzinfo is None:
                t_time = t_time.replace(tzinfo=timezone.utc)
            if start_time <= t_time <= end_time:
                filtered.append(t)
                
        return filtered

    def _build_markdown(self, summary: Dict[str, Any], trades: List[TradeJournal]) -> str:
        """Compose reports into structured markdown format."""
        header = (
            f"# TOJI {summary['report_type']} Performance Report\n"
            f"- **Report ID**: `{summary['report_id']}`\n"
            f"- **Period**: {summary['target_date']}\n"
            f"- **Generated At**: {summary['generated_at']}\n\n"
            f"## Summary Metrics\n"
            f"| Metric | Value |\n"
            f"| :--- | :--- |\n"
            f"| **Total Trades** | {summary['total_trades']} |\n"
            f"| **Total Realized PnL** | ${summary['total_pnl']:+,.2f} |\n"
            f"| **Win Rate** | {summary['win_rate']*100:.1f}% |\n\n"
        )
        
        details = "## Trade Details Logs\n"
        if not trades:
            details += "*No trades executed during this period.*\n"
        else:
            details += "| Trade ID | Symbol | Side | Quantity | Entry Price | Exit Price | PnL | Exit Time |\n"
            details += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            for t in trades:
                details += (
                    f"| `{t.order_id}` | {t.symbol} | {t.side} | {t.quantity:.4f} | "
                    f"${t.entry_price:,.2f} | ${t.exit_price:,.2f} | ${t.pnl:+,.2f} | {t.exit_time.isoformat()} |\n"
                )
                
        return header + details

    def _write_files(self, report_id: str, summary: Dict[str, Any], markdown_content: str, trades: List[TradeJournal]) -> None:
        """Write reports and metrics data to files (MD, JSON, CSV)."""
        # 1. Save Markdown log
        md_path = os.path.join(self.reports_dir, f"{report_id}.md")
        with open(md_path, "w") as f:
            f.write(markdown_content)

        # 2. Save JSON summary
        json_path = os.path.join(self.reports_dir, f"{report_id}.json")
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=4)

        # 3. Save CSV details logs
        csv_path = os.path.join(self.reports_dir, f"{report_id}.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["trade_id", "symbol", "side", "quantity", "entry_price", "exit_price", "pnl", "exit_time"])
            for t in trades:
                writer.writerow([
                    t.order_id,
                    t.symbol,
                    t.side,
                    t.quantity,
                    t.entry_price,
                    t.exit_price,
                    t.pnl,
                    t.exit_time.isoformat()
                ])
        logger.info("Performance reports exported successfully to %s", self.reports_dir)
