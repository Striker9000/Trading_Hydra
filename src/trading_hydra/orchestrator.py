"""Trading loop orchestrator with 5-step execution and fail-closed safety"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .core.logging import get_logger
from .core.config import load_settings, load_bots_config
from .core.state import init_state_store, get_state, set_state
from .core.clock import get_market_clock
from .core.health import get_health_monitor
from .core.halt import get_halt_manager
from .services.alpaca_client import get_alpaca_client
from .services.exitbot import get_exitbot
from .services.portfolio import get_portfoliobot
from .services.execution import get_execution_service


@dataclass
class LoopResult:
    success: bool
    status: str
    summary: str
    timestamp: str


class TradingOrchestrator:
    def __init__(self):
        self._logger = get_logger()
        self._clock = get_market_clock()
        self._health = get_health_monitor()
        self._halt = get_halt_manager()
        self._alpaca = get_alpaca_client()
        self._exitbot = get_exitbot()
        self._portfoliobot = get_portfoliobot()
        self._execution = get_execution_service()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return

        self._logger.log("orchestrator_init", {})
        init_state_store()
        self._initialized = True
        self._logger.log("orchestrator_ready", {})

    def run_loop(self) -> LoopResult:
        self.initialize()

        timestamp = datetime.utcnow().isoformat() + "Z"
        self._logger.log("loop_start", {"timestamp": timestamp})

        equity = 0.0
        day_start_equity = 0.0
        enabled_bots = []
        errors = []

        init_ok, equity, day_start_equity, init_error = self._step_initialize()
        if not init_ok:
            errors.append(init_error)

        should_continue = True
        halt_reason = ""

        if init_ok:
            exitbot_result = self._step_exitbot(equity, day_start_equity)
            should_continue = exitbot_result.should_continue
            halt_reason = exitbot_result.halt_reason
            if not should_continue:
                errors.append(halt_reason)
        else:
            should_continue = False
            halt_reason = f"Init failed: {init_error}"
            self._logger.log("loop_init_failed", {"error": init_error})

        if should_continue:
            portfolio_result = self._step_portfoliobot(equity)
            if portfolio_result.budgets_set:
                enabled_bots = portfolio_result.enabled_bots
            else:
                errors.append(portfolio_result.error or "Budgets not set")

        bots_run = []
        if should_continue and enabled_bots:
            exec_result = self._step_execution(enabled_bots, equity)
            bots_run = exec_result.bots_run
            errors.extend(exec_result.errors)

        result = self._step_finalize(bots_run, errors, halt_reason)

        self._logger.log("loop_end", {
            "success": result.success,
            "status": result.status,
            "bots_run": len(bots_run),
            "errors": len(errors)
        })

        return result

    def _step_initialize(self):
        self._logger.log("step_1_init", {})

        # Validate inputs
        if not self._alpaca.has_credentials():
            error = "ALPACA_KEY and ALPACA_SECRET required"
            self._logger.log("step_1_no_credentials", {"error": error})
            self._health.record_api_failure(error)
            return False, 0.0, 0.0, error

        # Retry account fetch with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                account = self._alpaca.get_account()
                equity = account.equity

                # Validate account data before proceeding
                if equity <= 0:
                    error = f"Invalid account equity: {equity}"
                    self._logger.error(error)
                    return False, 0.0, 0.0, error

                if account.status != "ACTIVE":
                    error = f"Account not active: {account.status}"
                    self._logger.warn(error)
                    # Continue with warning but don't fail

                break

            except Exception as e:
                error = f"Failed to fetch account (attempt {attempt + 1}): {e}"
                self._logger.error(error)

                if attempt < max_retries - 1:
                    # Wait before retry: 1s, 2s, 4s
                    import time
                    wait_time = 2 ** attempt
                    self._logger.log("retry_wait", {"seconds": wait_time})
                    time.sleep(wait_time)
                    continue
                else:
                    # Final attempt failed
                    return False, 0.0, 0.0, error

        date_string = self._clock.get_date_string()
        day_start_key = f"day_start_equity_{date_string}"

        day_start_equity = get_state(day_start_key)
        if not day_start_equity or day_start_equity < 1000:  # Reset if unreasonably low
            day_start_equity = equity
            set_state(day_start_key, day_start_equity)
            set_state("day_start_equity", day_start_equity)
            self._logger.log("step_1_day_start_reset", {
                "date": date_string,
                "day_start_equity": day_start_equity,
                "current_equity": equity,
                "reason": "new_day_or_invalid_value"
            })
        else:
            # Ensure day_start_equity is reasonable - if too low, reset it
            if day_start_equity < equity * 0.1:  # If day start is less than 10% of current equity
                self._logger.log("step_1_equity_reset", {
                    "old_day_start": day_start_equity,
                    "new_day_start": equity,
                    "reason": "day_start_too_low"
                })
                day_start_equity = equity
                set_state(day_start_key, day_start_equity)
                set_state("day_start_equity", day_start_equity)

        self._halt.clear_if_expired()

        self._logger.log("step_1_ok", {
            "equity": equity,
            "day_start_equity": day_start_equity
        })

        return True, equity, day_start_equity, ""

    def _step_exitbot(self, equity: float, day_start_equity: float):
        self._logger.log("step_2_exitbot", {})
        return self._exitbot.run(equity, day_start_equity)

    def _step_portfoliobot(self, equity: float):
        self._logger.log("step_3_portfoliobot", {})
        return self._portfoliobot.run(equity)

    def _step_execution(self, enabled_bots, equity: float):
        self._logger.log("step_4_execution", {"enabled_bots": enabled_bots})
        return self._execution.run(enabled_bots, equity)

    def _step_finalize(self, bots_run, errors, halt_reason):
        self._logger.log("step_5_finalize", {})

        timestamp = datetime.utcnow().isoformat() + "Z"
        is_halted = self._halt.is_halted()
        has_errors = len(errors) > 0
        bots_ran = len(bots_run) > 0

        if is_halted:
            status = f"HALTED: {halt_reason}"
            success = True
        elif has_errors and not bots_ran:
            is_init_error = any(
                "credentials" in e.lower() or
                "init" in e.lower() or
                "budgets" in e.lower()
                for e in errors
            )
            if is_init_error:
                status = "FAIL_CLOSED: System failed safely without trading"
                success = True
            else:
                status = f"ERROR: {'; '.join(errors)}"
                success = False
        elif not bots_ran:
            status = "SKIPPED: No bots ran"
            success = True
        elif has_errors:
            status = f"PARTIAL: {len(bots_run)} bots with {len(errors)} errors"
            success = False
        else:
            status = f"OK: {len(bots_run)} bots ran successfully"
            success = True

        summary = f"""
Trading Loop Summary:
- Status: {status}
- Bots run: {', '.join(bots_run) if bots_run else 'None'}
- Errors: {'; '.join(errors) if errors else 'None'}
- Timestamp: {timestamp}
""".strip()

        self._logger.log("loop_complete", {
            "status": status,
            "bots_run": bots_run,
            "errors": errors,
            "success": success,
            "timestamp": timestamp
        })

        # Validate outputs before returning
        if not isinstance(success, bool):
            success = bool(success)
        if not isinstance(status, str):
            status = str(status)
        if not isinstance(summary, str):
            summary = str(summary)
        if not isinstance(timestamp, str):
            timestamp = str(timestamp)

        return LoopResult(
            success=success,
            status=status,
            summary=summary,
            timestamp=timestamp
        )


_orchestrator: Optional[TradingOrchestrator] = None


def get_orchestrator() -> TradingOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TradingOrchestrator()
    return _orchestrator