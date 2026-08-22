"""CLI command parser and execution controller.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from research_platform.paper_dashboard.interfaces import IConsoleController
from research_platform.paper_dashboard.models import ConsoleCommand

logger = logging.getLogger(__name__)


class ConsoleController(IConsoleController):
    """Parses text commands and updates paper session settings."""

    def __init__(self, orchestrator: Any) -> None:
        self._orchestrator = orchestrator

    def execute_command_text(self, cmd_text: str) -> str:
        """Parse string commands and execute actions."""
        parts = cmd_text.strip().split()
        if not parts:
            return "ERROR: Empty command input."

        cmd_name = parts[0].upper()
        params = {}
        status = "SUCCESS"
        err_msg = None
        result_msg = ""

        try:
            if cmd_name == "START_SESSION":
                if len(parts) < 3:
                    raise ValueError("Usage: START_SESSION <account_id> <initial_balance>")
                account_id = parts[1]
                balance = float(parts[2])
                params = {"account_id": account_id, "balance": str(balance)}
                
                # Execute session start
                session = self._orchestrator.paper_trading.start_paper_session(account_id, balance)
                result_msg = f"SUCCESS: Started session '{session.session_id}' for account '{account_id}' with balance {balance}."

            elif cmd_name == "STOP_SESSION":
                stopped = self._orchestrator.paper_trading.stop_paper_session()
                if stopped:
                    result_msg = f"SUCCESS: Stopped active session '{stopped.session_id}'."
                else:
                    result_msg = "SUCCESS: No active session was running."

            elif cmd_name == "SET_ROUTING_MODE":
                if len(parts) < 2:
                    raise ValueError("Usage: SET_ROUTING_MODE <SIMULATION|PAPER|LIVE>")
                mode = parts[1].upper()
                params = {"mode": mode}
                self._orchestrator.paper_market.execution_router.set_mode(mode)
                result_msg = f"SUCCESS: Execution router mode changed to '{mode}'."

            elif cmd_name == "SHOW_METRICS":
                summary = self._orchestrator.refresh_dashboard()
                result_msg = (
                    f"--- TOJI Paper Dashboard ---\n"
                    f"Account: {summary.account_id}\n"
                    f"Equity: {summary.equity:.2f}\n"
                    f"Cash: {summary.cash:.2f}\n"
                    f"Realized PnL: {summary.realized_pnl:.2f}\n"
                    f"Unrealized PnL: {summary.unrealized_pnl:.2f}\n"
                    f"Peak Drawdown: {summary.drawdown * 100.0:.2f}%\n"
                    f"Routing Mode: {summary.routing_mode}\n"
                    f"Session Active: {summary.is_session_active}\n"
                    f"---------------------------"
                )

            else:
                raise ValueError(f"Unknown command '{cmd_name}'")

        except Exception as e:
            status = "FAILED"
            err_msg = str(e)
            result_msg = f"ERROR: {err_msg}"
            logger.error("Console command failed: %s", e)

        # Log command execution
        cmd_record = ConsoleCommand(
            command_id=f"cmd-{uuid.uuid4().hex[:8]}",
            command_name=cmd_name,
            parameters=params,
            timestamp=datetime.now(timezone.utc),
            status=status,
            error_message=err_msg
        )
        self._orchestrator.repository.save_command(cmd_record)

        return result_msg
