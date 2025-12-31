"""PortfolioBot service for dynamic budget allocation"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from ..core.logging import get_logger
from ..core.config import load_settings, load_bots_config
from ..core.state import get_state, set_state
from ..core.risk import dollars_from_pct


@dataclass
class PortfolioBotResult:
    budgets_set: bool
    daily_risk: float
    enabled_bots: List[str]
    error: str


class PortfolioBot:
    def __init__(self):
        self._logger = get_logger()
    
    def run(self, equity: float) -> PortfolioBotResult:
        self._logger.log("portfoliobot_start", {"equity": equity})
        
        try:
            config = load_bots_config()
            settings = load_settings()
        except Exception as e:
            self._logger.error(f"PortfolioBot config load failed: {e}")
            return PortfolioBotResult(
                budgets_set=False,
                daily_risk=0,
                enabled_bots=[],
                error=str(e)
            )
        
        portfolio_config = config.get("portfoliobot", {})
        
        if not portfolio_config.get("enabled", True):
            self._logger.log("portfoliobot_disabled", {})
            return PortfolioBotResult(
                budgets_set=False,
                daily_risk=0,
                enabled_bots=[],
                error=""
            )
        
        day_start_equity = get_state("day_start_equity", equity) or equity
        risk_config = settings.get("risk", {})
        max_loss_pct = risk_config.get("global_max_daily_loss_pct", 1.0)
        daily_risk = dollars_from_pct(day_start_equity, max_loss_pct)
        
        buckets = portfolio_config.get("buckets", {})
        mom_bucket = daily_risk * (buckets.get("momentum_bucket_pct_of_daily_risk", 50) / 100)
        opt_bucket = daily_risk * (buckets.get("options_bucket_pct_of_daily_risk", 50) / 100)
        cry_bucket = daily_risk * (buckets.get("crypto_bucket_pct_of_daily_risk", 25) / 100)
        
        guardrails = portfolio_config.get("guardrails", {})
        per_min = daily_risk * (guardrails.get("per_bot_min_pct_of_daily_risk", 10) / 100)
        per_max = daily_risk * (guardrails.get("per_bot_max_pct_of_daily_risk", 50) / 100)
        
        enabled_bots = []
        
        momentum_bots = config.get("momentum_bots", [])
        enabled_momentum = [b for b in momentum_bots if b.get("enabled", False)]
        num_mom = max(1, len(enabled_momentum))
        mom_each = max(per_min, min(per_max, mom_bucket / num_mom))
        
        for bot in momentum_bots:
            bot_id = bot.get("bot_id", "")
            risk_cfg = bot.get("risk", {})
            
            set_state(f"budgets.{bot_id}.max_daily_loss", mom_each)
            set_state(f"budgets.{bot_id}.max_open_risk", mom_each * 2)
            set_state(f"budgets.{bot_id}.max_trades_per_day", risk_cfg.get("max_trades_per_day", 5))
            set_state(f"budgets.{bot_id}.max_concurrent_positions", risk_cfg.get("max_concurrent_positions", 2))
            set_state(f"bots.{bot_id}.allowed", True)
            set_state(f"bots.{bot_id}.enabled", bot.get("enabled", False))
            
            if bot.get("enabled", False):
                enabled_bots.append(bot_id)
        
        optionsbot = config.get("optionsbot", {})
        if optionsbot.get("enabled", False):
            bot_id = optionsbot.get("bot_id", "opt_core")
            risk_cfg = optionsbot.get("risk", {})
            
            set_state(f"budgets.{bot_id}.max_daily_loss", opt_bucket)
            set_state(f"budgets.{bot_id}.max_open_risk", opt_bucket * 2)
            set_state(f"budgets.{bot_id}.max_trades_per_day", risk_cfg.get("max_trades_per_day", 3))
            set_state(f"budgets.{bot_id}.max_concurrent_positions", risk_cfg.get("max_concurrent_positions", 2))
            set_state(f"bots.{bot_id}.allowed", True)
            set_state(f"bots.{bot_id}.enabled", True)
            enabled_bots.append(bot_id)
        
        cryptobot = config.get("cryptobot", {})
        if cryptobot.get("enabled", False):
            bot_id = cryptobot.get("bot_id", "crypto_core")
            risk_cfg = cryptobot.get("risk", {})
            
            set_state(f"budgets.{bot_id}.max_daily_loss", cry_bucket)
            set_state(f"budgets.{bot_id}.max_open_risk", cry_bucket * 2)
            set_state(f"budgets.{bot_id}.max_trades_per_day", risk_cfg.get("max_trades_per_day", 5))
            set_state(f"budgets.{bot_id}.max_concurrent_positions", risk_cfg.get("max_concurrent_positions", 3))
            set_state(f"bots.{bot_id}.allowed", True)
            set_state(f"bots.{bot_id}.enabled", True)
            enabled_bots.append(bot_id)
        
        self._logger.log("portfoliobot_budgets", {
            "equity": equity,
            "day_start_equity": day_start_equity,
            "daily_risk": round(daily_risk, 2),
            "mom_bucket": round(mom_bucket, 2),
            "opt_bucket": round(opt_bucket, 2),
            "cry_bucket": round(cry_bucket, 2),
            "mom_each": round(mom_each, 2),
            "enabled_bots": enabled_bots
        })
        
        return PortfolioBotResult(
            budgets_set=True,
            daily_risk=daily_risk,
            enabled_bots=enabled_bots,
            error=""
        )


_portfoliobot: Optional[PortfolioBot] = None


def get_portfoliobot() -> PortfolioBot:
    global _portfoliobot
    if _portfoliobot is None:
        _portfoliobot = PortfolioBot()
    return _portfoliobot
