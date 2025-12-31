"""Crypto trading bot implementation with BTC/ETH strategies"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import ta
import pandas as pd
import random

from ..core.logging import get_logger
from ..core.state import get_state, set_state
from ..services.alpaca_client import get_alpaca_client
from ..services.mock_data import get_mock_provider, is_development_mode


class CryptoBot:
    """Bitcoin and Ethereum trading bot with momentum strategies"""

    def __init__(self, bot_id: str = "crypto_core"):
        self.bot_id = bot_id
        self.pairs = ["BTC/USD", "ETH/USD"]
        self._logger = get_logger()
        self._alpaca = get_alpaca_client()

    def execute(self, max_daily_loss: float) -> Dict[str, Any]:
        """Execute crypto trading strategy"""

        results = {
            "trades_attempted": 0,
            "positions_managed": 0,
            "signals": {},
            "errors": []
        }

        try:
            # Get current positions
            positions = self._alpaca.get_positions()
            crypto_positions = [p for p in positions if any(pair.replace("/", "") in p.symbol for pair in self.pairs)]

            # Manage existing positions first
            for position in crypto_positions:
                try:
                    self._manage_position(position)
                    results["positions_managed"] += 1
                except Exception as e:
                    results["errors"].append(f"Position management {position.symbol}: {e}")

            # Look for new entries
            max_positions = 2
            if len(crypto_positions) < max_positions:
                for pair in self.pairs:
                    if results["trades_attempted"] >= 1:  # Limit new trades per cycle
                        break

                    try:
                        signal = self._generate_signal(pair)
                        results["signals"][pair] = signal

                        if signal["action"] == "buy":
                            trade_result = self._execute_trade(pair, signal, max_daily_loss)
                            if trade_result["success"]:
                                results["trades_attempted"] += 1
                            else:
                                results["errors"].append(f"{pair}: {trade_result['error']}")

                    except Exception as e:
                        results["errors"].append(f"Signal generation {pair}: {e}")

            self._logger.log("crypto_bot_execution_complete", {
                "bot_id": self.bot_id,
                "results": results,
                "max_daily_loss": max_daily_loss
            })

        except Exception as e:
            self._logger.error(f"Crypto bot execution failed: {e}")
            results["errors"].append(str(e))

        return results

    def _generate_signal(self, pair: str) -> Dict[str, Any]:
        """Generate trading signal using technical analysis"""

        signal = {
            "pair": pair,
            "action": "hold",
            "confidence": 0.0,
            "price": 0.0,
            "indicators": {}
        }

        try:
            # Get current quote
            quote = self._alpaca.get_latest_quote(pair, asset_class="crypto")
            current_price = (quote["bid"] + quote["ask"]) / 2
            signal["price"] = current_price

            # Simple momentum strategy based on price action
            # In production, you would use historical data and technical indicators

            # Get recent price history from state (simplified)
            price_history_key = f"price_history.{pair.replace('/', '')}"
            price_history = get_state(price_history_key, [])

            # Add current price to history
            price_history.append({
                "price": current_price,
                "timestamp": datetime.utcnow().isoformat()
            })

            # Keep only last 20 prices
            if len(price_history) > 20:
                price_history = price_history[-20:]

            # Update state
            set_state(price_history_key, price_history)

            # Generate mock signals during development mode
            if is_development_mode():
                mock_provider = get_mock_provider()
                if mock_provider.should_generate_signal(pair, "crypto"):
                    mock_action = mock_provider.get_mock_signal_action()
                    if mock_action != "hold":
                        signal["action"] = mock_action
                        signal["confidence"] = random.uniform(0.4, 0.9)
                        signal["mock_signal"] = True
            else:
                # Simple momentum signal
                if len(price_history) >= 5:
                    recent_prices = [p["price"] for p in price_history[-5:]]
                    sma5 = sum(recent_prices) / len(recent_prices)

                    # Buy signal if price is above 5-period moving average
                    if current_price > sma5 * 1.001:  # 0.1% threshold
                        signal["action"] = "buy"
                        signal["confidence"] = min(0.8, (current_price / sma5 - 1) * 100)

                    signal["indicators"]["sma5"] = sma5
                    signal["indicators"]["price_vs_sma"] = (current_price / sma5 - 1) * 100

        except Exception as e:
            self._logger.error(f"Signal generation failed for {pair}: {e}")
            signal["error"] = str(e)

        return signal

    def _execute_trade(self, pair: str, signal: Dict[str, Any], max_daily_loss: float) -> Dict[str, Any]:
        """Execute crypto trade with proper position sizing"""

        result = {"success": False, "error": None, "order_id": None}

        try:
            # Ensure minimum order size above Alpaca's $10 requirement
            min_order = 15.0  # $15 minimum with buffer
            dollar_amount = max(min_order, max_daily_loss * 0.8)

            # Skip if budget too small for meaningful crypto trade
            if dollar_amount < min_order:
                result["error"] = f"Budget ${dollar_amount:.2f} below crypto minimum ${min_order}"
                self._logger.log("crypto_budget_too_small", {
                    "pair": pair,
                    "budget": dollar_amount,
                    "minimum": min_order
                })
                return result

            # Place market buy order
            order_response = self._alpaca.place_market_order(
                symbol=pair,
                side="buy",
                notional=dollar_amount
            )

            result["success"] = True
            result["order_id"] = order_response.get("id")

            # Log successful trade
            self._logger.log("crypto_trade_executed", {
                "pair": pair,
                "side": "buy",
                "notional": dollar_amount,
                "order_id": order_response.get("id"),
                "signal_confidence": signal.get("confidence", 0),
                "entry_price": signal.get("price", 0)
            })

            # Store trade info in state
            import time
            trade_key = f"trades.{self.bot_id}.{int(time.time())}"
            set_state(trade_key, {
                "pair": pair,
                "side": "buy",
                "notional": dollar_amount,
                "timestamp": time.time(),
                "order_id": order_response.get("id"),
                "entry_price": signal.get("price", 0),
                "signal": signal
            })

        except Exception as e:
            result["error"] = str(e)
            self._logger.error(f"Trade execution failed for {pair}: {e}")

        return result

    def _manage_position(self, position):
        """Manage existing crypto position with risk management"""

        try:
            # Calculate current P&L percentage
            if abs(position.market_value) > 0:
                pnl_pct = (position.unrealized_pl / abs(position.market_value)) * 100
            else:
                return

            # Risk management rules from config
            stop_loss_pct = -0.75  # 0.75% stop loss
            take_profit_pct = 1.50  # 1.50% take profit

            should_close = False
            close_reason = ""

            # Check stop loss
            if pnl_pct <= stop_loss_pct:
                should_close = True
                close_reason = "stop_loss"

            # Check take profit
            elif pnl_pct >= take_profit_pct:
                should_close = True
                close_reason = "take_profit"

            # Time-based exit (4 hours max hold from config)
            # This would require checking entry time from state

            if should_close:
                self._close_position(position, close_reason)

        except Exception as e:
            self._logger.error(f"Position management failed for {position.symbol}: {e}")

    def _close_position(self, position, reason: str):
        """Close position with market order"""

        try:
            # Determine order side
            side = "sell" if position.side == "long" else "buy"
            qty = abs(float(position.qty))

            # Place market order to close
            order_response = self._alpaca.place_market_order(
                symbol=position.symbol,
                side=side,
                qty=qty
            )

            self._logger.log("crypto_position_closed", {
                "symbol": position.symbol,
                "side": side,
                "qty": qty,
                "reason": reason,
                "pnl": position.unrealized_pl,
                "order_id": order_response.get("id")
            })

        except Exception as e:
            self._logger.error(f"Failed to close position {position.symbol}: {e}")