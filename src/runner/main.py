"""Main runner for Trading Hydra - long-running process with config-driven loop"""
import os
import sys
import signal
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from trading_hydra.core.config import load_settings
from trading_hydra.core.logging import get_logger
from trading_hydra.core.state import close_state_store
from trading_hydra.orchestrator import get_orchestrator

_running = True


def signal_handler(signum, frame):
    global _running
    logger = get_logger()
    logger.log("shutdown_signal", {"signal": signum})
    _running = False


def main():
    global _running
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger = get_logger()
    logger.log("runner_start", {"pid": os.getpid()})
    
    try:
        settings = load_settings()
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)
    
    loop_interval = settings.get("runner", {}).get("loop_interval_seconds", 5)
    logger.log("runner_config", {"loop_interval_seconds": loop_interval})
    
    orchestrator = get_orchestrator()
    
    try:
        orchestrator.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        sys.exit(1)
    
    loop_count = 0
    
    logger.log("runner_loop_starting", {"interval": loop_interval})
    
    while _running:
        loop_count += 1
        loop_start = time.time()
        
        logger.log("runner_loop_iteration", {
            "loop_count": loop_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        
        try:
            result = orchestrator.run_loop()
            logger.log("runner_loop_result", {
                "loop_count": loop_count,
                "success": result.success,
                "status": result.status
            })
        except Exception as e:
            logger.error(f"Loop error: {e}", loop_count=loop_count)
        
        elapsed = time.time() - loop_start
        sleep_time = max(0, loop_interval - elapsed)
        
        if sleep_time > 0 and _running:
            logger.log("runner_sleeping", {"seconds": round(sleep_time, 2)})
            time.sleep(sleep_time)
    
    logger.log("runner_shutdown", {"total_loops": loop_count})
    close_state_store()
    logger.log("runner_stopped", {})


if __name__ == "__main__":
    main()
