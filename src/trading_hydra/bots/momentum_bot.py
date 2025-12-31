
"""Momentum trading bot for individual stocks"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import random

from ..core.logging import get_logger
from ..core.state import get_state, set_state
from ..services.alpaca_client import get_alpaca_client
from ..services.mock_data import get_mock_provider, is_development_mode


class MomentumBot:
    """Single stock momentum trading bot"""
    
    def __init__(self, bot_id: str, ticker: str):
        self.bot_id = bot_id
        self.ticker = ticker
        self._logger = get_logger()
        self._alpaca = get_alpaca_client()
    
    def execute(self, max_daily_loss: float) -> Dict[str, Any]:
        """Execute momentum trading strategy"""
        
        results = {
            "trades_attempted": 0,
            "positions_managed": 0,
            "signal": {},
            "errors": []
        }
        
        try:
            # Get current positions for this ticker
            positions = self._alpaca.get_positions()
            ticker_positions = [p for p in positions if p.symbol == self.ticker]
            
            # Manage existing positions
            for position in ticker_positions:
                try:
                    self._manage_position(position, max_daily_loss)
                    results["positions_managed"] += 1
                except Exception as e:
                    results["errors"].append(f"Position management {self.ticker}: {e}")
            
            # Look for new entry if no position exists (max 1 concurrent position from config)
            if len(ticker_positions) == 0:
                try:
                    signal = self._generate_momentum_signal()
                    results["signal"] = signal
                    
                    if signal["action"] in ["buy", "sell"]:
                        trade_result = self._execute_trade(signal, max_daily_loss)
                        if trade_result["success"]:
                            results["trades_attempted"] += 1
                        else:
                            results["errors"].append(f"{self.ticker}: {trade_result['error']}")
                            
                except Exception as e:
                    results["errors"].append(f"Signal generation {self.ticker}: {e}")
            
            self._logger.log("momentum_bot_execution_complete", {
                "bot_id": self.bot_id,
                "ticker": self.ticker,
                "results": results,
                "max_daily_loss": max_daily_loss
            })
            
        except Exception as e:
            self._logger.error(f"Momentum bot execution failed for {self.ticker}: {e}")
            results["errors"].append(str(e))
        
        return results
    
    def _generate_momentum_signal(self) -> Dict[str, Any]:
        """Generate momentum signal for the ticker"""
        
        signal = {
            "ticker": self.ticker,
            "action": "hold",
            "confidence": 0.0,
            "price": 0.0,
            "indicators": {}
        }
        
        try:
            # Get current quote
            quote = self._alpaca.get_latest_quote(self.ticker, asset_class="stock")
            current_price = (quote["bid"] + quote["ask"]) / 2
            signal["price"] = current_price
            
            # Simple momentum strategy
            # In production, you'd analyze volume, RSI, MACD, etc.
            
            # Get price history from state
            price_history_key = f"price_history.{self.ticker}"
            price_history = get_state(price_history_key, [])
            
            # Add current price
            price_history.append({
                "price": current_price,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Keep last 10 prices
            if len(price_history) > 10:
                price_history = price_history[-10:]
            
            set_state(price_history_key, price_history)
            
            # Generate signal based on price trend
            if len(price_history) >= 3:
                prices = [p["price"] for p in price_history[-3:]]
                
                # Check for uptrend
                if prices[-1] > prices[-2] > prices[-3]:
                    # Additional confirmation: current price > moving average
                    avg_price = sum(prices) / len(prices)
                    if current_price > avg_price * 1.002:  # 0.2% above average
                        signal["action"] = "buy"
                        signal["confidence"] = min(0.8, (current_price / avg_price - 1) * 50)
                
                # Check for downtrend (for short selling, if enabled)
                elif prices[-1] < prices[-2] < prices[-3]:
                    avg_price = sum(prices) / len(prices)
                    if current_price < avg_price * 0.998:  # 0.2% below average
                        signal["action"] = "sell"
                        signal["confidence"] = min(0.8, (avg_price / current_price - 1) * 50)
                
                signal["indicators"]["trend_prices"] = prices
                signal["indicators"]["avg_price"] = sum(prices) / len(prices)
            
            # Market session filter (from config: trade between 06:35 - 09:30)
            current_time = datetime.now().time()
            trade_start = datetime.strptime("06:35", "%H:%M").time()
            trade_end = datetime.strptime("09:30", "%H:%M").time()
            
            # Use mock signals during development mode
            if is_development_mode():
                mock_provider = get_mock_provider()
                if mock_provider.should_generate_signal(self.ticker, "momentum"):
                    mock_action = mock_provider.get_mock_signal_action()
                    if mock_action != "hold":
                        signal["action"] = mock_action
                        signal["confidence"] = random.uniform(0.3, 0.8)
                        signal["mock_signal"] = True
                        self._logger.log("momentum_mock_signal_generated", {
                            "ticker": self.ticker,
                            "action": mock_action,
                            "confidence": signal["confidence"]
                        })
            elif not (trade_start <= current_time <= trade_end):
                signal["action"] = "hold"
                signal["out_of_hours"] = True
            
        except Exception as e:
            self._logger.error(f"Momentum signal generation failed for {self.ticker}: {e}")
            signal["error"] = str(e)
        
        return signal
    
    def _execute_trade(self, signal: Dict[str, Any], max_daily_loss: float) -> Dict[str, Any]:
        """Execute momentum trade"""
        
        result = {"success": False, "error": None, "order_id": None}
        
        try:
            # Position sizing: use 80% of daily budget
            dollar_amount = max(5.0, max_daily_loss * 0.8)
            
            # Place market order
            order_response = self._alpaca.place_market_order(
                symbol=self.ticker,
                side=signal["action"],
                notional=dollar_amount
            )
            
            result["success"] = True
            result["order_id"] = order_response.get("id")
            
            self._logger.log("momentum_trade_executed", {
                "ticker": self.ticker,
                "side": signal["action"],
                "notional": dollar_amount,
                "order_id": order_response.get("id"),
                "signal_confidence": signal.get("confidence", 0),
                "entry_price": signal.get("price", 0)
            })
            
            # Store trade in state
            import time
            trade_key = f"trades.{self.bot_id}.{int(time.time())}"
            set_state(trade_key, {
                "ticker": self.ticker,
                "side": signal["action"],
                "notional": dollar_amount,
                "timestamp": time.time(),
                "order_id": order_response.get("id"),
                "entry_price": signal.get("price", 0),
                "signal": signal
            })
            
        except Exception as e:
            result["error"] = str(e)
            self._logger.error(f"Momentum trade execution failed for {self.ticker}: {e}")
        
        return result
    
    def _manage_position(self, position, max_daily_loss: float):
        """Manage existing momentum position with stops and targets"""
        
        try:
            # Calculate P&L percentage
            if abs(position.market_value) > 0:
                pnl_pct = (position.unrealized_pl / abs(position.market_value)) * 100
            else:
                return
            
            # Risk management from config
            stop_loss_pct = -0.50  # 0.50% stop loss
            take_profit_pct = 1.00  # 1.00% take profit
            
            should_close = False
            close_reason = ""
            
            # Check exit conditions
            if pnl_pct <= stop_loss_pct:
                should_close = True
                close_reason = "stop_loss"
            elif pnl_pct >= take_profit_pct:
                should_close = True
                close_reason = "take_profit"
            
            # Time-based exit (25 minutes from config)
            # Would need entry timestamp from state to implement
            
            # Session-based exit (manage until 12:55 from config)
            current_time = datetime.now().time()
            manage_until = datetime.strptime("12:55", "%H:%M").time()
            if current_time >= manage_until:
                should_close = True
                close_reason = "session_end"
            
            if should_close:
                self._close_position(position, close_reason)
                
        except Exception as e:
            self._logger.error(f"Momentum position management failed for {self.ticker}: {e}")
    
    def _close_position(self, position, reason: str):
        """Close momentum position"""
        
        try:
            side = "sell" if position.side == "long" else "buy"
            qty = abs(float(position.qty))
            
            order_response = self._alpaca.place_market_order(
                symbol=position.symbol,
                side=side,
                qty=qty
            )
            
            self._logger.log("momentum_position_closed", {
                "ticker": self.ticker,
                "side": side,
                "qty": qty,
                "reason": reason,
                "pnl": position.unrealized_pl,
                "order_id": order_response.get("id")
            })
            
        except Exception as e:
            self._logger.error(f"Failed to close momentum position {self.ticker}: {e}")
