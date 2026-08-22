#!/usr/bin/env python3
"""TOJI Runtime Supervisor Process.
Monitors both the FastAPI API and the Paper Trading Engine processes, auto-restarting the engine if it crashes.
"""

import sys
import os
import time
import signal
import logging
import subprocess
from datetime import datetime, timezone

from toji_platform.runtime.state import RuntimeStateManager, RuntimeState
from research_platform.platform.bootstrap import bootstrap_platform
from research_platform.platform.service_registry import ServiceRegistry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] TOJI_Supervisor: %(message)s"
)
logger = logging.getLogger("TOJI_Supervisor")

## ── Startup Validation Check ──
toji_mode = os.getenv("TOJI_MODE", "PAPER").upper()
db_status = "configured" if os.getenv("DATABASE_URL") else "missing"
redis_status = "configured" if os.getenv("REDIS_URL") else "missing"

admin_key = os.getenv("TOJI_ADMIN_API_KEY")
analyst_key = os.getenv("TOJI_ANALYST_API_KEY")
admin_status = "PRESENT" if admin_key else "MISSING"
analyst_status = "PRESENT" if analyst_key else "MISSING"

# Only perform full environment printing and fast-fail exit if not running in pytest
if "pytest" not in sys.modules and os.getenv("APP_ENV") != "testing":
    print("TOJI CONFIG CHECK\n", flush=True)
    print(f"Mode: {toji_mode}", flush=True)
    print(f"Database: {db_status}", flush=True)
    print(f"Redis: {redis_status}", flush=True)
    print(f"Admin key: {admin_status}", flush=True)
    print(f"Analyst key: {analyst_status}\n", flush=True)

    if toji_mode != "DEV":
        if not admin_key or admin_key == "toji_admin_secret_key_12345":
            logger.error("Supervisor validation failed: Insecure default or missing TOJI_ADMIN_API_KEY in PAPER/PROD mode!")
            sys.exit(1)
        if not analyst_key or analyst_key == "toji_analyst_secret_key_67890":
            logger.error("Supervisor validation failed: Insecure default or missing TOJI_ANALYST_API_KEY in PAPER/PROD mode!")
            sys.exit(1)

# Ensure MARKET_PROVIDER is set
if not os.getenv("MARKET_PROVIDER"):
    os.environ["MARKET_PROVIDER"] = "demo"

# Bootstrap the platform to obtain alert orchestrator
try:
    if "pytest" in sys.modules:
        container = ServiceRegistry().get_service("Container")
        event_bus = ServiceRegistry().get_service("EventBus")
        platform_app = None
    else:
        platform_app = bootstrap_platform()
        container = ServiceRegistry().get_service("Container")
        event_bus = ServiceRegistry().get_service("EventBus")
except Exception as e:
    logger.error("Failed to bootstrap platform in supervisor: %s", e)
    container = None
    event_bus = None


def send_telegram_alert(message: str) -> None:
    """Dispatches a notification via the alert orchestrator."""
    try:
        if container:
            alert_orch = container.resolve("AlertOrchestrator")
            if alert_orch:
                from research_platform.alerting.models import Alert, AlertSeverity, AlertChannel
                alert = Alert(
                    title="TOJI SUPERVISOR ALERT",
                    message=message,
                    severity=AlertSeverity.HIGH,
                    channels=[AlertChannel.TELEGRAM]
                )
                alert_orch.fire(alert)
    except Exception as e:
        logger.debug("Failed to dispatch telegram alert from supervisor: %s", e)


def main() -> None:
    import sys
    import os
    global platform_app, container, event_bus
    
    state_manager = RuntimeStateManager()
    state_manager.load()
    
    # Initialize supervisor state
    state_manager.set_state(RuntimeState.STARTING)
    if state_manager.redis_client:
        state_manager.redis_client.set("TOJI:paper_engine_status", "starting")
        
    api_port = os.getenv("TOJI_API_PORT", "8000")
    api_cmd = [sys.executable, "scripts/run_api.py", api_port]
    engine_cmd = [sys.executable, "scripts/run_paper_trading.py"]
    
    # Propagate host environment variables explicitly to child process
    env = os.environ.copy()
    
    use_thread = False
    if container is not None and event_bus is not None:
        if os.getenv("TOJI_SINGLE_KERNEL") != "false":
            if "pytest" not in sys.modules or os.getenv("TOJI_SINGLE_KERNEL") == "true":
                use_thread = True
            
    api_thread = None
    api_process = None
    
    # Define API runner for thread mode
    def run_api_thread():
        import uvicorn
        from backend.main import app
        uvicorn.run(app, host="0.0.0.0", port=int(api_port), log_level="info")
        
    if use_thread:
        logger.info("Starting FastAPI API service (via background thread)...")
        import threading
        api_thread = threading.Thread(target=run_api_thread, name="TOJI_API_Thread", daemon=True)
        api_thread.start()
        
        logger.info("Starting Paper Trading Engine (via PaperRunner thread)...")
        from scripts.run_paper_trading import PaperRunner
        runner = PaperRunner(container=container, event_bus=event_bus)
        runner.start()
        engine_process = None
    else:
        logger.info("Starting FastAPI API service (via subprocess fallback)...")
        api_process = subprocess.Popen(
            api_cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env
        )
        
        logger.info("Starting Paper Trading Engine (via subprocess fallback)...")
        engine_process = subprocess.Popen(
            engine_cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env
        )
        runner = None
    
    if state_manager.redis_client:
        state_manager.redis_client.set("TOJI:paper_engine_status", "running")
    state_manager.set_state(RuntimeState.RUNNING)
    
    def shutdown_handler(signum, frame):
        logger.info("Shutdown signal received. Terminating processes...")
        if api_process is not None:
            api_process.terminate()
        if engine_process is not None:
            engine_process.terminate()
        if runner is not None:
            try:
                runner.stop()
            except Exception as e:
                logger.error("Error stopping PaperRunner: %s", e)
        try:
            if platform_app:
                platform_app.shutdown()
        except Exception as e:
            logger.error("Error shutting down platform: %s", e)
        sys.exit(0)
        
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    restart_count = state_manager.restart_count
    last_heartbeat_time = time.time()
    
    while True:
        try:
            time.sleep(1.0)
        except KeyboardInterrupt:
            shutdown_handler(signal.SIGINT, None)
            
        # Check API status
        api_exited = False
        exit_code = None
        if use_thread:
            if api_thread is not None and not api_thread.is_alive():
                api_exited = True
                exit_code = -1
        else:
            if api_process is not None and api_process.poll() is not None:
                api_exited = True
                exit_code = api_process.poll()

        if api_exited:
            logger.error("FastAPI service exited. Restarting...")
            error_reason = f"FastAPI service exited or crashed with code {exit_code}."
            
            restart_count += 1
            state_manager.restart_count = restart_count
            state_manager.persist()
            
            msg = (
                f"🚨 TOJI SERVICE RESTARTED\n\n"
                f"Service:\n"
                f"FastAPI\n\n"
                f"Reason:\n"
                f"{error_reason}\n\n"
                f"Restart count:\n"
                f"{restart_count}"
            )
            send_telegram_alert(msg)
            
            logger.info("Restarting FastAPI service (Count: %d)...", restart_count)
            if use_thread:
                import threading
                api_thread = threading.Thread(target=run_api_thread, name="TOJI_API_Thread", daemon=True)
                api_thread.start()
            else:
                api_process = subprocess.Popen(
                    api_cmd,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    env=env
                )
            
        # Check Engine status
        if engine_process is not None:
            if engine_process.poll() is not None:
                exit_code = engine_process.poll()
                logger.error("Paper Trading Engine crashed with exit code %s", exit_code)
                error_reason = f"Paper Trading Engine exited or crashed with code {exit_code}."
                
                if state_manager.redis_client:
                    state_manager.redis_client.set("TOJI:paper_engine_status", "dead")
                state_manager.set_state(RuntimeState.DEGRADED)
                
                restart_count += 1
                state_manager.restart_count = restart_count
                state_manager.persist()
                
                msg = (
                    f"🚨 TOJI SERVICE RESTARTED (TOJI ENGINE RESTARTED)\n\n"
                    f"Service:\n"
                    f"Paper Trading Engine\n\n"
                    f"Reason:\n"
                    f"{error_reason}\n\n"
                    f"Restart count:\n"
                    f"{restart_count}"
                )
                send_telegram_alert(msg)
                
                logger.info("Restarting Paper Trading Engine (Count: %d)...", restart_count)
                engine_process = subprocess.Popen(
                    engine_cmd,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    env=env
                )
                if state_manager.redis_client:
                    state_manager.redis_client.set("TOJI:paper_engine_status", "running")
                state_manager.set_state(RuntimeState.RUNNING)
        elif runner is not None:
            if not runner.running:
                logger.error("Paper Trading Engine thread stopped. Restarting...")
                error_reason = "Paper Trading Engine thread stopped or crashed."
                
                if state_manager.redis_client:
                    state_manager.redis_client.set("TOJI:paper_engine_status", "dead")
                state_manager.set_state(RuntimeState.DEGRADED)
                
                restart_count += 1
                state_manager.restart_count = restart_count
                state_manager.persist()
                
                msg = (
                    f"🚨 TOJI SERVICE RESTARTED (TOJI ENGINE RESTARTED)\n\n"
                    f"Service:\n"
                    f"Paper Trading Engine\n\n"
                    f"Reason:\n"
                    f"{error_reason}\n\n"
                    f"Restart count:\n"
                    f"{restart_count}"
                )
                send_telegram_alert(msg)
                
                logger.info("Restarting Paper Trading Engine (Count: %d)...", restart_count)
                runner = PaperRunner(container=container, event_bus=event_bus)
                runner.start()
                if state_manager.redis_client:
                    state_manager.redis_client.set("TOJI:paper_engine_status", "running")
                state_manager.set_state(RuntimeState.RUNNING)
 
        # 60 seconds heartbeat print
        curr_time = time.time()
        if curr_time - last_heartbeat_time >= 60.0:
            last_heartbeat_time = curr_time
            state_manager.load()
            last_tick = "N/A"
            if state_manager.last_tick_time:
                last_tick = state_manager.last_tick_time.isoformat()
            
            engine_status = 'ALIVE'
            if engine_process is not None:
                engine_status = 'ALIVE' if engine_process.poll() is None else 'DEAD'
            elif runner is not None:
                engine_status = 'ALIVE' if runner.running else 'DEAD'
            
            api_alive = 'DEAD'
            if api_process is not None:
                api_alive = 'ALIVE' if api_process.poll() is None else 'DEAD'
            elif api_thread is not None:
                api_alive = 'ALIVE' if api_thread.is_alive() else 'DEAD'

            heartbeat_msg = (
                "SUPERVISOR:\n"
                f"API: {api_alive}\n"
                f"PAPER_ENGINE: {engine_status}\n"
                f"LAST_TICK_TIME: {last_tick}\n"
                f"RESTART_COUNT: {restart_count}"
            )
            print(heartbeat_msg, flush=True)
 
if __name__ == "__main__":
    main()
