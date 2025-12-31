"""Execution service for running trading bots with real Alpaca integration"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import random
import time
from datetime import datetime, timedelta

from ..core.logging import get_logger
from ..core.config import load_bots_config
from ..core.state import get_state, set_state
from ..core.health import get_health_monitor
from ..core.risk import valid_budget


@dataclass
class ExecutionResult:
    bots_run: List[str]
    trades_attempted: int
    positions_managed: int
    errors: List[str]


class ExecutionService:
    def __init__(self):
        self._logger = get_logger()
        self._health = get_health_monitor()

    def run(self, enabled_bots: List[str], equity: float) -> ExecutionResult:
        self._logger.log("execution_start", {"enabled_bots": enabled_bots, "equity": equity})

        bots_run = []
        errors = []
        trades_attempted = 0
        positions_managed = 0

        for bot_id in enabled_bots:
            try:
                is_enabled = get_state(f"bots.{bot_id}.enabled", False)
                is_allowed = get_state(f"bots.{bot_id}.allowed", False)
                max_daily_loss = get_state(f"budgets.{bot_id}.max_daily_loss", 0)

                if not is_enabled or not is_allowed:
                    self._logger.log("execution_bot_skipped", {
                        "bot_id": bot_id,
                        "reason": "not_enabled_or_allowed"
                    })
                    continue

                if not valid_budget(max_daily_loss):
                    self._logger.log("execution_bot_skipped", {
                        "bot_id": bot_id,
                        "reason": "invalid_budget",
                        "max_daily_loss": max_daily_loss
                    })
                    continue

                self._logger.log("execution_bot_preflight_ok", {
                    "bot_id": bot_id,
                    "max_daily_loss": round(max_daily_loss, 2)
                })

                # Execute bot-specific trading logic
                if bot_id == "crypto_core":
                    result = self._execute_crypto_bot(bot_id, max_daily_loss)
                    trades_attempted += result.get("trades_attempted", 0)
                    positions_managed += result.get("positions_managed", 0)
                elif bot_id.startswith("mom_"):
                    result = self._execute_momentum_bot(bot_id, max_daily_loss)
                    trades_attempted += result.get("trades_attempted", 0)
                    positions_managed += result.get("positions_managed", 0)
                elif bot_id == "opt_core":
                    result = self._execute_options_bot(bot_id, max_daily_loss)
                    trades_attempted += result.get("trades_attempted", 0)
                    positions_managed += result.get("positions_managed", 0)

                bots_run.append(bot_id)

            except Exception as e:
                self._logger.error(f"Bot {bot_id} execution error: {e}")
                errors.append(f"{bot_id}: {e}")

        self._health.record_price_tick()

        self._logger.log("execution_complete", {
            "bots_run": bots_run,
            "trades_attempted": trades_attempted,
            "positions_managed": positions_managed,
            "errors": errors
        })

        return ExecutionResult(
            bots_run=bots_run,
            trades_attempted=trades_attempted,
            positions_managed=positions_managed,
            errors=errors
        )

    def _execute_crypto_bot(self, bot_id: str, max_daily_loss: float) -> Dict[str, int]:
        """Execute crypto trading logic for BTC/USD and ETH/USD"""
        from ..services.alpaca_client import get_alpaca_client

        alpaca = get_alpaca_client()
        pairs = ["BTC/USD", "ETH/USD"]
        trades_attempted = 0
        positions_managed = 0

        # Get current positions to avoid over-trading
        current_positions = alpaca.get_positions()
        crypto_positions = [p for p in current_positions if any(pair.replace("/", "") in str(p.symbol) for pair in pairs)]
        positions_managed = len(crypto_positions)

        self._logger.log("crypto_bot_start", {
            "pairs": pairs,
            "max_daily_loss": round(max_daily_loss, 2),
            "existing_positions": positions_managed
        })

        # Check position limits from config
        max_positions = 2  # From bots.yaml crypto config

        # Manage existing positions first (stop losses, take profits)
        for position in crypto_positions:
            try:
                self._manage_crypto_position(position, bot_id)
                positions_managed += 1
            except Exception as e:
                self._logger.error(f"Position management error for {position.symbol}: {e}")

        # Look for new entries if under position limit
        if len(crypto_positions) < max_positions:
            for pair in pairs:
                if trades_attempted >= 2:  # Max 2 new trades per cycle
                    break

                try:
                    # Check if we already have this position
                    symbol_clean = pair.replace("/", "")
                    has_position = any(symbol_clean in str(p.symbol) for p in crypto_positions)

                    if has_position:
                        self._logger.log("crypto_skip_existing_position", {
                            "symbol": pair,
                            "reason": "already_have_position"
                        })
                        continue

                    # Get current market data
                    try:
                        quote = alpaca.get_latest_quote(pair, asset_class="crypto")
                        mid_price = (quote["bid"] + quote["ask"]) / 2
                    except Exception as e:
                        self._logger.warn(f"Could not get quote for {pair}: {e}")
                        continue

                    # Simple momentum signal (replace with your strategy)
                    signal = self._generate_crypto_signal(pair, mid_price, bot_id)

                    if signal == "buy":
                        # Position sizing: ensure minimum $10 for crypto (Alpaca requirement)
                        dollar_amount = max(10.0, min(50.0, max_daily_loss * 0.8))

                        # Use qty instead of notional for crypto to avoid time_in_force issues
                        # Estimate qty based on current price
                        estimated_qty = dollar_amount / mid_price

                        order_response = alpaca.place_market_order(
                            symbol=pair,
                            side="buy",
                            qty=round(estimated_qty, 6)  # Crypto allows up to 6 decimal places
                        )

                        self._logger.log("crypto_order_placed", {
                            "symbol": pair,
                            "side": "buy",
                            "notional": dollar_amount, # Logged as notional for consistency, though qty was used for order
                            "qty": round(estimated_qty, 6),
                            "order_id": order_response.get("id"),
                            "status": order_response.get("status"),
                            "paper_trading": alpaca.is_paper,
                            "mid_price": mid_price
                        })

                        trades_attempted += 1

                        # Update state tracking
                        trade_key = f"trades.{bot_id}.{int(time.time())}"
                        set_state(trade_key, {
                            "symbol": pair,
                            "side": "buy",
                            "notional": dollar_amount,
                            "qty": round(estimated_qty, 6),
                            "timestamp": time.time(),
                            "order_id": order_response.get("id"),
                            "entry_price": mid_price
                        })

                    else:
                        self._logger.log("crypto_signal_hold", {
                            "symbol": pair,
                            "signal": signal,
                            "action": "no_trade",
                            "mid_price": mid_price
                        })

                except Exception as e:
                    self._logger.error(f"Crypto trading error for {pair}: {e}")

        self._logger.log("crypto_bot_complete", {
            "trades_attempted": trades_attempted,
            "positions_managed": positions_managed,
            "pairs_analyzed": len(pairs),
            "max_daily_loss": round(max_daily_loss, 2),
            "paper_trading": alpaca.is_paper
        })

        return {"trades_attempted": trades_attempted, "positions_managed": positions_managed}

    def _execute_momentum_bot(self, bot_id: str, max_daily_loss: float) -> Dict[str, int]:
        """Execute momentum trading logic for stocks like AAPL"""
        from ..services.alpaca_client import get_alpaca_client

        alpaca = get_alpaca_client()
        trades_attempted = 0
        positions_managed = 0

        # Get ticker from bot_id (e.g., mom_AAPL -> AAPL)
        ticker = bot_id.replace("mom_", "")

        # Get current positions
        current_positions = alpaca.get_positions()
        stock_positions = [p for p in current_positions if str(p.symbol) == ticker]
        positions_managed = len(stock_positions)

        self._logger.log("momentum_bot_start", {
            "ticker": ticker,
            "max_daily_loss": round(max_daily_loss, 2),
            "existing_positions": positions_managed
        })

        # Manage existing positions
        for position in stock_positions:
            try:
                self._manage_stock_position(position, bot_id, max_daily_loss)
                positions_managed += 1
            except Exception as e:
                self._logger.error(f"Position management error for {position.symbol}: {e}")

        # Look for new entries if no position exists
        max_positions = 1  # From config: max_concurrent_positions: 1
        if len(stock_positions) < max_positions:
            try:
                # Get current market data
                quote = alpaca.get_latest_quote(ticker, asset_class="stock")
                mid_price = (quote["bid"] + quote["ask"]) / 2

                # Generate momentum signal
                signal = self._generate_momentum_signal(ticker, mid_price, bot_id)

                if signal in ["buy", "sell"]:
                    # Position sizing: 75% of allocated budget, minimum $1.00 for Alpaca
                    dollar_amount = max(1.00, min(20.0, max_daily_loss * 0.75))

                    order_response = alpaca.place_market_order(
                        symbol=ticker,
                        side=signal,
                        notional=dollar_amount
                    )

                    self._logger.log("momentum_order_placed", {
                        "ticker": ticker,
                        "side": signal,
                        "notional": dollar_amount,
                        "order_id": order_response.get("id"),
                        "status": order_response.get("status"),
                        "paper_trading": alpaca.is_paper,
                        "mid_price": mid_price
                    })

                    trades_attempted += 1

                    # Track trade
                    trade_key = f"trades.{bot_id}.{int(time.time())}"
                    set_state(trade_key, {
                        "symbol": ticker,
                        "side": signal,
                        "notional": dollar_amount,
                        "timestamp": time.time(),
                        "order_id": order_response.get("id"),
                        "entry_price": mid_price
                    })

                else:
                    self._logger.log("momentum_signal_hold", {
                        "ticker": ticker,
                        "signal": signal,
                        "action": "no_trade",
                        "mid_price": mid_price
                    })

            except Exception as e:
                self._logger.error(f"Momentum trading error for {ticker}: {e}")

        self._logger.log("momentum_bot_complete", {
            "ticker": ticker,
            "trades_attempted": trades_attempted,
            "positions_managed": positions_managed,
            "max_daily_loss": round(max_daily_loss, 2),
            "paper_trading": alpaca.is_paper
        })

        return {"trades_attempted": trades_attempted, "positions_managed": positions_managed}

    def _execute_options_bot(self, bot_id: str, max_daily_loss: float) -> Dict[str, int]:
        """Execute enhanced options trading with multiple strategies"""
        from ..bots.options_bot import OptionsBot
        
        try:
            # Use the enhanced options bot
            options_bot = OptionsBot(bot_id)
            result = options_bot.execute(max_daily_loss)
            
            self._logger.log("enhanced_options_bot_execution_complete", {
                "bot_id": bot_id,
                "trades_attempted": result.get("trades_attempted", 0),
                "positions_managed": result.get("positions_managed", 0),
                "strategies_analyzed": result.get("strategies_analyzed", 0),
                "errors": result.get("errors", []),
                "max_daily_loss": round(max_daily_loss, 2)
            })
            
            return {
                "trades_attempted": result.get("trades_attempted", 0),
                "positions_managed": result.get("positions_managed", 0)
            }
            
        except Exception as e:
            self._logger.error(f"Enhanced options bot execution failed: {e}")
            return {"trades_attempted": 0, "positions_managed": 0}

    def _generate_crypto_signal(self, pair: str, price: float, bot_id: str) -> str:
        """Generate trading signal for crypto pair"""
        # Simple random signal for demonstration
        # Replace with your actual crypto strategy (RSI, MACD, etc.)
        signals = ["buy", "hold", "hold", "hold", "hold"]  # 20% buy probability
        return random.choice(signals)

    def _generate_momentum_signal(self, ticker: str, price: float, bot_id: str) -> str:
        """Generate momentum signal for stock"""
        # Simple random signal for demonstration
        # Replace with your actual momentum strategy
        signals = ["buy", "sell", "hold", "hold", "hold", "hold"]  # 33% action probability
        return random.choice(signals)

    def _generate_options_signal(self, ticker: str, price: float, bot_id: str) -> str:
        """Generate options signal"""
        # Simple random signal for demonstration
        # Replace with your actual options strategy
        signals = ["buy_call", "buy_put", "hold", "hold", "hold"]  # 40% action probability
        return random.choice(signals)

    def _manage_crypto_position(self, position, bot_id: str):
        """Manage existing crypto position with stops and targets"""
        from ..services.alpaca_client import get_alpaca_client

        alpaca = get_alpaca_client()

        # Get current quote for position
        try:
            quote = alpaca.get_latest_quote(position.symbol, asset_class="crypto")
            current_price = (quote["bid"] + quote["ask"]) / 2
        except:
            return  # Skip if can't get quote

        # Calculate P&L
        unrealized_pnl_pct = (position.unrealized_pl / abs(position.market_value)) * 100

        # Exit conditions from config: stop_loss_pct: 0.75, take_profit_pct: 1.50
        if unrealized_pnl_pct <= -75:  # Stop loss
            self._close_position(position, "stop_loss", alpaca)
        elif unrealized_pnl_pct >= 150:  # Take profit
            self._close_position(position, "take_profit", alpaca)

        # Time-based exit (4 hours from config: time_stop_minutes: 240)
        # This would require tracking entry time from state

    def _manage_stock_position(self, position, bot_id: str, max_daily_loss: float):
        """Manage existing stock position"""
        from ..services.alpaca_client import get_alpaca_client

        alpaca = get_alpaca_client()

        # Similar position management logic for stocks
        unrealized_pnl_pct = (position.unrealized_pl / abs(position.market_value)) * 100

        # Exit conditions from momentum config: stop_loss_pct: 0.50, take_profit_pct: 1.00
        if unrealized_pnl_pct <= -50:  # Stop loss
            self._close_position(position, "stop_loss", alpaca)
        elif unrealized_pnl_pct >= 100:  # Take profit
            self._close_position(position, "take_profit", alpaca)

    def _close_position(self, position, reason: str, alpaca):
        """Close a position"""
        try:
            if position.side == "long":
                side = "sell"
            else:
                side = "buy"

            order_response = alpaca.place_market_order(
                symbol=position.symbol,
                side=side,
                qty=abs(float(position.qty))
            )

            self._logger.log("position_closed", {
                "symbol": position.symbol,
                "reason": reason,
                "side": side,
                "qty": abs(float(position.qty)),
                "unrealized_pl": position.unrealized_pl,
                "order_id": order_response.get("id")
            })

        except Exception as e:
            self._logger.error(f"Failed to close position {position.symbol}: {e}")


_execution_service: Optional[ExecutionService] = None


def get_execution_service() -> ExecutionService:
    global _execution_service
    if _execution_service is None:
        _execution_service = ExecutionService()
    return _execution_service