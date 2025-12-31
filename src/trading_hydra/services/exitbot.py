"""ExitBot service for kill-switch and safety checks"""
from typing import Dict, Any, Optional
from dataclasses import dataclass

from ..core.logging import get_logger
from ..core.config import load_settings, load_bots_config
from ..core.state import get_state, set_state
from ..core.health import get_health_monitor
from ..core.halt import get_halt_manager
from ..core.risk import dollars_from_pct
from .alpaca_client import get_alpaca_client


@dataclass
class ExitBotResult:
    should_continue: bool
    is_halted: bool
    halt_reason: str
    equity: float
    pnl: float


class ExitBot:
    def __init__(self):
        self._logger = get_logger()
        self._health = get_health_monitor()
        self._halt = get_halt_manager()
        self._alpaca = get_alpaca_client()
    
    def run(self, equity: float, day_start_equity: float) -> ExitBotResult:
        self._logger.log("exitbot_start", {"equity": equity, "day_start": day_start_equity})
        
        try:
            config = load_bots_config()
            settings = load_settings()
        except Exception as e:
            self._logger.error(f"ExitBot config load failed: {e}")
            return ExitBotResult(
                should_continue=False,
                is_halted=True,
                halt_reason=f"Config load failed: {e}",
                equity=equity,
                pnl=0
            )
        
        exitbot_config = config.get("exitbot", {})
        
        if not exitbot_config.get("enabled", True):
            self._logger.log("exitbot_disabled", {})
            pnl = equity - day_start_equity
            return ExitBotResult(
                should_continue=True,
                is_halted=False,
                halt_reason="",
                equity=equity,
                pnl=pnl
            )
        
        if self._halt.is_halted():
            status = self._halt.get_status()
            self._logger.log("exitbot_already_halted", {"reason": status.reason})
            return ExitBotResult(
                should_continue=False,
                is_halted=True,
                halt_reason=status.reason,
                equity=equity,
                pnl=0
            )
        
        health = self._health.get_snapshot()
        kill_conditions = exitbot_config.get("kill_conditions", {})
        cooloff = exitbot_config.get("cooloff_minutes", 60)
        
        if not health.ok and kill_conditions.get("api_failure_halt", True):
            reason = f"HEALTH_FAIL: {health.reason}"
            self._halt.set_halt(reason, cooloff)
            self._logger.log("exitbot_halt", {"reason": reason})
            
            if self._alpaca.has_credentials():
                result = self._alpaca.flatten()
                if not result["success"]:
                    reason = f"{reason} + FLATTEN_FAILED: {result['error']}"
                    self._logger.log("exitbot_flatten_failed", {"error": result["error"]})
            else:
                self._logger.log("exitbot_flatten_skipped", {"reason": "no_credentials"})
            
            return ExitBotResult(
                should_continue=False,
                is_halted=True,
                halt_reason=reason,
                equity=equity,
                pnl=0
            )
        
        pnl = equity - day_start_equity
        risk_config = settings.get("risk", {})
        max_loss_pct = risk_config.get("global_max_daily_loss_pct", 1.0)
        max_loss = dollars_from_pct(day_start_equity, max_loss_pct)
        
        if pnl <= -max_loss and kill_conditions.get("max_daily_loss_halt", True):
            reason = f"MAX_DAILY_LOSS: pnl={pnl:.2f} <= -{max_loss:.2f}"
            self._halt.set_halt(reason, cooloff)
            self._logger.log("exitbot_halt", {"reason": reason, "pnl": pnl, "max_loss": max_loss})
            
            if self._alpaca.has_credentials():
                result = self._alpaca.flatten()
                if not result["success"]:
                    reason = f"{reason} + FLATTEN_FAILED: {result['error']}"
                    self._logger.error("Flatten failed", error=result["error"])
            else:
                self._logger.error("Cannot flatten - no credentials with positions at risk")
                reason = f"{reason} + CANNOT_FLATTEN: no credentials"
            
            return ExitBotResult(
                should_continue=False,
                is_halted=True,
                halt_reason=reason,
                equity=equity,
                pnl=pnl
            )
        
        self._logger.log("exitbot_ok", {
            "equity": equity,
            "pnl": round(pnl, 2),
            "max_loss": round(max_loss, 2)
        })
        
        return ExitBotResult(
            should_continue=True,
            is_halted=False,
            halt_reason="",
            equity=equity,
            pnl=pnl
        )


_exitbot: Optional[ExitBot] = None


def get_exitbot() -> ExitBot:
    global _exitbot
    if _exitbot is None:
        _exitbot = ExitBot()
    return _exitbot
