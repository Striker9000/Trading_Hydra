"""Health monitoring for API and data freshness"""
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from .state import get_state, set_state
from .config import load_settings
from .logging import get_logger


@dataclass
class HealthSnapshot:
    ok: bool
    reason: str
    api_failures: int
    last_price_tick: Optional[str]
    stale_seconds: float


class HealthMonitor:
    def __init__(self):
        self._settings = None
        self._logger = get_logger()
    
    @property
    def settings(self) -> Dict[str, Any]:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings
    
    def record_api_failure(self, error: str = "") -> None:
        count = get_state("health.api_failure_count", 0) or 0
        set_state("health.api_failure_count", count + 1)
        set_state("health.last_api_failure", datetime.utcnow().isoformat() + "Z")
        self._logger.warn(f"API failure recorded, count: {count + 1}", error=error)
    
    def record_price_tick(self) -> None:
        set_state("health.last_price_tick", datetime.utcnow().isoformat() + "Z")
        set_state("health.api_failure_count", 0)
    
    def get_snapshot(self) -> HealthSnapshot:
        health_config = self.settings.get("health", {})
        max_failures = health_config.get("max_api_failures_in_window", 5)
        stale_threshold = health_config.get("max_price_staleness_seconds", 15)
        
        api_failures = get_state("health.api_failure_count", 0) or 0
        last_tick_str = get_state("health.last_price_tick")
        
        stale_seconds = 0.0
        
        if last_tick_str:
            try:
                last_tick = datetime.fromisoformat(last_tick_str.replace("Z", "+00:00"))
                stale_seconds = (datetime.now(last_tick.tzinfo) - last_tick).total_seconds()
            except:
                pass
        
        ok = True
        reason = "OK"
        
        if api_failures >= max_failures:
            ok = False
            reason = f"API failures ({api_failures}) >= max ({max_failures})"
        elif last_tick_str and stale_seconds > stale_threshold:
            ok = False
            reason = f"Data stale ({stale_seconds:.0f}s > {stale_threshold}s)"
        
        return HealthSnapshot(
            ok=ok,
            reason=reason,
            api_failures=api_failures,
            last_price_tick=last_tick_str,
            stale_seconds=stale_seconds
        )


_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
