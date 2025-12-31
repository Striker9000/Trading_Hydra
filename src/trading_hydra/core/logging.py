"""JSONL file logger for trading events"""
import os
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional

_jsonl_logger: Optional["JsonlLogger"] = None


class JsonlLogger:
    def __init__(self, log_path: str = "./logs/app.jsonl"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self._recent_logs = []  # Track recent logs for execution service
        self._setup_console_logging()
    
    def _setup_console_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self._console = logging.getLogger("trading_hydra")
    
    def log(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        if data is None:
            data = {}
        
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            **data
        }
        
        # Track recent logs (keep last 100)
        self._recent_logs.append(event_type)
        if len(self._recent_logs) > 100:
            self._recent_logs.pop(0)
        
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            self._console.error(f"Failed to write JSONL: {e}")
        
        level = logging.WARNING if "halt" in event_type or "error" in event_type else logging.INFO
        self._console.log(level, f"[{event_type}] {json.dumps(data)}")
    
    def info(self, msg: str, **kwargs: Any) -> None:
        self.log("info", {"message": msg, **kwargs})
    
    def warn(self, msg: str, **kwargs: Any) -> None:
        self.log("warn", {"message": msg, **kwargs})
    
    def error(self, msg: str, **kwargs: Any) -> None:
        self.log("error", {"message": msg, **kwargs})


def get_logger() -> JsonlLogger:
    global _jsonl_logger
    if _jsonl_logger is None:
        _jsonl_logger = JsonlLogger()
    return _jsonl_logger
