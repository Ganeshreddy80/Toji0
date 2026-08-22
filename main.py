"""TOJI Unified executable entry point.
"""

from __future__ import annotations

import logging
import signal
import sys
import time

from research_platform.platform.bootstrap import bootstrap_platform

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    # 1. Boot platform application
    app = bootstrap_platform()

    # 2. Setup termination signal handlers
    def signal_handler(sig, frame):
        logger.info("Signal intercept received (%s). Shutting down platform...", sig)
        app.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("TOJI Platform V1 is fully online and ready.")
    
    # Idle loop
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt intercepted.")
        app.shutdown()


if __name__ == "__main__":
    main()
