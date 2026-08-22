#!/usr/bin/env python3
"""Daily Learning Report Dispatcher.
Retrieves completed trades from TradeMemoryEngine, compiles learning lessons, and dispatches to Telegram.
"""

import sys
import logging
from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry
from research_platform.trade_memory.engine import TradeMemoryEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DailyLearningReport")

def main() -> None:
    # Initialize container to access alert orchestrator
    try:
        app = bootstrap_platform()
        container = ServiceRegistry().get_service("Container")
    except Exception as e:
        logger.error("Failed to bootstrap platform: %s", e)
        container = None

    # Load trade memory and compile report
    memory = TradeMemoryEngine()
    report_msg = memory.generate_daily_learning_report()
    
    # Output to console
    print("\n" + "="*40)
    print("CONPILED DAILY LEARNING REPORT:")
    print("="*40)
    print(report_msg)
    print("="*40 + "\n")

    # Send to Telegram
    if container:
        try:
            alert_orch = container.resolve("AlertOrchestrator")
            if alert_orch:
                from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel
                alert = Alert(
                    title="🧠 TOJI DAILY LEARNING REPORT",
                    message=report_msg,
                    severity=AlertSeverity.HIGH,
                    channels=[AlertChannel.TELEGRAM]
                )
                alert_orch.fire(alert)
                logger.info("Daily Learning Report successfully dispatched to Telegram.")
        except Exception as e:
            logger.error("Failed to send learning report to Telegram: %s", e)

if __name__ == "__main__":
    main()
