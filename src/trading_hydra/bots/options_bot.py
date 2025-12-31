
"""Enhanced Options trading bot with multiple profitable strategies"""
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta, time
import math
import random
import numpy as np
from enum import Enum

from ..core.logging import get_logger
from ..core.state import get_state, set_state
from ..services.alpaca_client import get_alpaca_client


class OptionStrategy(Enum):
    BULL_PUT_SPREAD = "bull_put_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    IRON_CONDOR = "iron_condor"
    BUTTERFLY = "butterfly"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    COVERED_CALL = "covered_call"


class MarketRegime(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    HIGH_VOLATILITY = "high_vol"
    LOW_VOLATILITY = "low_vol"


class OptionsBot:
    """Enhanced options trading bot with multiple profitable strategies"""
    
    def __init__(self, bot_id: str = "opt_core"):
        self.bot_id = bot_id
        self.tickers = ["SPY", "QQQ", "IWM", "SPX"]  # Added more liquid options
        self._logger = get_logger()
        self._alpaca = get_alpaca_client()
        
        # Strategy configurations optimized for $50-500 profit targets
        self.strategy_configs = {
            OptionStrategy.BULL_PUT_SPREAD: {
                "min_credit": 0.30,
                "max_credit": 2.50,
                "spread_width_range": (3, 10),
                "short_delta_range": (-0.30, -0.15),
                "long_delta_range": (-0.15, -0.05),
                "profit_target": 0.50,  # 50% of credit
                "stop_loss": 2.0,  # 200% of credit (stop at -100% P&L)
                "min_dte": 7,
                "max_dte": 45,
                "ideal_iv_rank": (20, 80),  # Higher IV for credit spreads
                "market_bias": [MarketRegime.BULLISH, MarketRegime.NEUTRAL]
            },
            OptionStrategy.BEAR_CALL_SPREAD: {
                "min_credit": 0.30,
                "max_credit": 2.50,
                "spread_width_range": (3, 10),
                "short_delta_range": (0.15, 0.30),
                "long_delta_range": (0.05, 0.15),
                "profit_target": 0.50,
                "stop_loss": 2.0,
                "min_dte": 7,
                "max_dte": 45,
                "ideal_iv_rank": (20, 80),
                "market_bias": [MarketRegime.BEARISH, MarketRegime.NEUTRAL]
            },
            OptionStrategy.IRON_CONDOR: {
                "min_credit": 0.50,
                "max_credit": 3.00,
                "spread_width_range": (5, 15),
                "short_delta_range": (-0.20, 0.20),  # Both sides
                "profit_target": 0.25,  # 25% of credit (more conservative)
                "stop_loss": 2.5,
                "min_dte": 21,
                "max_dte": 60,
                "ideal_iv_rank": (30, 90),
                "market_bias": [MarketRegime.NEUTRAL, MarketRegime.LOW_VOLATILITY]
            },
            OptionStrategy.STRADDLE: {
                "min_cost": 2.00,
                "max_cost": 15.00,
                "delta_range": (-0.55, -0.45),  # ATM
                "profit_target": 0.30,  # 30% profit
                "stop_loss": 0.50,  # 50% loss
                "min_dte": 14,
                "max_dte": 60,
                "ideal_iv_rank": (10, 40),  # Lower IV to buy
                "market_bias": [MarketRegime.HIGH_VOLATILITY]
            }
        }
        
        # Risk management
        self.max_position_size = 500.0  # Max $ per trade
        self.max_concurrent_trades = 3
        
        # Market hours (EST - your note about PST is noted)
        self.trading_hours = (time(9, 30), time(15, 30))  # Stop 30min before close
        
    def execute(self, max_daily_loss: float) -> Dict[str, Any]:
        """Execute enhanced options trading with multiple strategies"""
        
        results = {
            "trades_attempted": 0,
            "positions_managed": 0,
            "strategies_analyzed": 0,
            "market_analysis": {},
            "errors": []
        }
        
        try:
            # Check trading hours (EST)
            current_time = datetime.now().time()
            if not self._is_trading_hours(current_time):
                self._logger.log("options_bot_outside_hours", {
                    "current_time": current_time.strftime("%H:%M"),
                    "trading_hours": f"{self.trading_hours[0]}-{self.trading_hours[1]} EST",
                    "action": "skip_trading"
                })
                return results
            
            # Get current positions and manage them
            positions = self._alpaca.get_positions()
            options_positions = [p for p in positions if self._is_options_position(p)]
            
            for position in options_positions:
                try:
                    self._manage_options_position(position)
                    results["positions_managed"] += 1
                except Exception as e:
                    results["errors"].append(f"Position management {position.symbol}: {e}")
            
            # Check if we can open new positions
            if len(options_positions) < self.max_concurrent_trades:
                for ticker in self.tickers:
                    if results["trades_attempted"] >= 2:  # Limit new trades per cycle
                        break
                        
                    try:
                        # Market analysis
                        market_analysis = self._analyze_market_conditions(ticker)
                        results["market_analysis"][ticker] = market_analysis
                        
                        # Strategy selection based on market conditions
                        best_strategy = self._select_optimal_strategy(market_analysis)
                        results["strategies_analyzed"] += 1
                        
                        if best_strategy:
                            # Execute the selected strategy
                            trade_result = self._execute_strategy(
                                ticker, best_strategy, market_analysis, max_daily_loss
                            )
                            
                            if trade_result["success"]:
                                results["trades_attempted"] += 1
                                self._logger.log("options_strategy_executed", {
                                    "ticker": ticker,
                                    "strategy": best_strategy.value,
                                    "expected_profit": trade_result.get("expected_profit", 0),
                                    "risk": trade_result.get("risk", 0)
                                })
                            else:
                                results["errors"].append(f"{ticker} {best_strategy.value}: {trade_result.get('error', 'Unknown error')}")
                        
                    except Exception as e:
                        results["errors"].append(f"Strategy analysis {ticker}: {e}")
            
            self._logger.log("enhanced_options_bot_complete", {
                "bot_id": self.bot_id,
                "results": results,
                "max_daily_loss": max_daily_loss
            })
            
        except Exception as e:
            self._logger.error(f"Enhanced options bot execution failed: {e}")
            results["errors"].append(str(e))
        
        return results
    
    def _is_trading_hours(self, current_time: time) -> bool:
        """Check if current time is within trading hours (EST)"""
        start_time, end_time = self.trading_hours
        return start_time <= current_time <= end_time
    
    def _analyze_market_conditions(self, ticker: str) -> Dict[str, Any]:
        """Analyze market conditions to determine optimal strategy"""
        
        analysis = {
            "ticker": ticker,
            "price": 0.0,
            "trend": MarketRegime.NEUTRAL,
            "volatility": MarketRegime.LOW_VOLATILITY,
            "iv_rank": 50.0,
            "support_levels": [],
            "resistance_levels": [],
            "volume_profile": "normal",
            "earnings_near": False,
            "recommended_strategies": []
        }
        
        try:
            # Get current price
            quote = self._alpaca.get_latest_quote(ticker, asset_class="stock")
            current_price = (quote["bid"] + quote["ask"]) / 2
            analysis["price"] = current_price
            
            # Simulate market analysis (in production, use real technical analysis)
            analysis.update(self._simulate_market_analysis(ticker, current_price))
            
            # Determine recommended strategies based on analysis
            analysis["recommended_strategies"] = self._get_strategy_recommendations(analysis)
            
        except Exception as e:
            self._logger.error(f"Market analysis failed for {ticker}: {e}")
            analysis["error"] = str(e)
        
        return analysis
    
    def _simulate_market_analysis(self, ticker: str, price: float) -> Dict[str, Any]:
        """Simulate comprehensive market analysis (replace with real analysis)"""
        
        # This simulates what would be real market analysis
        # In production, implement:
        # - RSI, MACD, Bollinger Bands
        # - Volume analysis
        # - Support/resistance levels
        # - IV rank/percentile
        # - Earnings calendar
        
        np.random.seed(int(datetime.now().timestamp()) % 1000)
        
        # Simulate trend analysis
        trend_score = np.random.normal(0, 1)
        if trend_score > 0.5:
            trend = MarketRegime.BULLISH
        elif trend_score < -0.5:
            trend = MarketRegime.BEARISH
        else:
            trend = MarketRegime.NEUTRAL
        
        # Simulate volatility analysis
        vol_score = np.random.uniform(0, 100)
        volatility = MarketRegime.HIGH_VOLATILITY if vol_score > 60 else MarketRegime.LOW_VOLATILITY
        
        # Simulate IV rank
        iv_rank = np.random.uniform(10, 90)
        
        # Simulate support/resistance
        support_levels = [price * 0.98, price * 0.95]
        resistance_levels = [price * 1.02, price * 1.05]
        
        return {
            "trend": trend,
            "volatility": volatility,
            "iv_rank": iv_rank,
            "support_levels": support_levels,
            "resistance_levels": resistance_levels,
            "volume_profile": "normal",
            "earnings_near": np.random.random() < 0.1  # 10% chance
        }
    
    def _get_strategy_recommendations(self, analysis: Dict[str, Any]) -> List[OptionStrategy]:
        """Get strategy recommendations based on market analysis"""
        
        recommendations = []
        trend = analysis["trend"]
        volatility = analysis["volatility"]
        iv_rank = analysis["iv_rank"]
        
        # High IV strategies (credit spreads, iron condors)
        if iv_rank > 50:
            if trend == MarketRegime.BULLISH:
                recommendations.extend([OptionStrategy.BULL_PUT_SPREAD, OptionStrategy.BEAR_CALL_SPREAD])
            elif trend == MarketRegime.BEARISH:
                recommendations.extend([OptionStrategy.BEAR_CALL_SPREAD, OptionStrategy.BULL_PUT_SPREAD])
            else:  # Neutral
                recommendations.append(OptionStrategy.IRON_CONDOR)
        
        # Low IV strategies (long options)
        if iv_rank < 40:
            if volatility == MarketRegime.HIGH_VOLATILITY:
                recommendations.append(OptionStrategy.STRADDLE)
        
        # Default to most conservative
        if not recommendations:
            recommendations.append(OptionStrategy.BULL_PUT_SPREAD)
        
        return recommendations
    
    def _select_optimal_strategy(self, market_analysis: Dict[str, Any]) -> Optional[OptionStrategy]:
        """Select the optimal strategy based on market conditions"""
        
        recommended = market_analysis.get("recommended_strategies", [])
        if not recommended:
            return None
        
        # For now, select the first recommended strategy
        # In production, you could score each strategy based on:
        # - Expected profit/loss ratio
        # - Probability of success
        # - Risk/reward
        # - Market fit
        
        return recommended[0]
    
    def _execute_strategy(self, ticker: str, strategy: OptionStrategy, 
                         market_analysis: Dict[str, Any], max_daily_loss: float) -> Dict[str, Any]:
        """Execute the selected options strategy"""
        
        result = {"success": False, "error": None, "expected_profit": 0, "risk": 0}
        
        try:
            underlying_price = market_analysis["price"]
            
            if strategy == OptionStrategy.BULL_PUT_SPREAD:
                return self._execute_bull_put_spread(ticker, underlying_price, max_daily_loss)
            elif strategy == OptionStrategy.BEAR_CALL_SPREAD:
                return self._execute_bear_call_spread(ticker, underlying_price, max_daily_loss)
            elif strategy == OptionStrategy.IRON_CONDOR:
                return self._execute_iron_condor(ticker, underlying_price, max_daily_loss)
            elif strategy == OptionStrategy.STRADDLE:
                return self._execute_straddle(ticker, underlying_price, max_daily_loss)
            else:
                result["error"] = f"Strategy {strategy.value} not implemented"
                
        except Exception as e:
            result["error"] = str(e)
            self._logger.error(f"Strategy execution failed: {e}")
        
        return result
    
    def _execute_bull_put_spread(self, ticker: str, underlying_price: float, 
                                max_daily_loss: float) -> Dict[str, Any]:
        """Execute bull put spread strategy"""
        
        result = {"success": False, "error": None, "expected_profit": 0, "risk": 0}
        
        try:
            # Generate options chain
            options_chain = self._generate_realistic_options_chain(ticker, underlying_price, "put")
            if not options_chain:
                result["error"] = "No options chain available"
                return result
            
            # Find optimal strikes
            config = self.strategy_configs[OptionStrategy.BULL_PUT_SPREAD]
            spread = self._find_optimal_vertical_spread(options_chain, config, underlying_price)
            
            if not spread:
                result["error"] = "No suitable spread found"
                return result
            
            short_put, long_put = spread
            credit = short_put["bid"] - long_put["ask"]
            spread_width = short_put["strike"] - long_put["strike"]
            max_loss = spread_width - credit
            
            # Position sizing for target profit
            target_profit = 75  # Target $75 profit
            contracts = max(1, min(10, int(target_profit / (credit * 100))))  # 1-10 contracts
            
            position_cost = max_loss * contracts * 100
            if position_cost > min(max_daily_loss * 0.5, self.max_position_size):
                result["error"] = "Position size too large"
                return result
            
            # For demo: simulate with underlying stock position
            underlying_order = self._alpaca.place_market_order(
                symbol=ticker,
                side="buy",
                notional=min(25.0, max_daily_loss * 0.3)  # Conservative simulation
            )
            
            # Store trade details
            trade_data = {
                "strategy": "bull_put_spread",
                "ticker": ticker,
                "contracts": contracts,
                "short_strike": short_put["strike"],
                "long_strike": long_put["strike"],
                "credit_per_contract": credit,
                "total_credit": credit * contracts * 100,
                "max_loss": max_loss * contracts * 100,
                "breakeven": short_put["strike"] - credit,
                "profit_target": credit * contracts * 100 * config["profit_target"],
                "timestamp": datetime.now().timestamp(),
                "order_id": underlying_order.get("id"),
                "underlying_price": underlying_price
            }
            
            trade_key = f"options_trades.{self.bot_id}.{int(trade_data['timestamp'])}"
            set_state(trade_key, trade_data)
            
            result.update({
                "success": True,
                "expected_profit": trade_data["profit_target"],
                "risk": trade_data["max_loss"],
                "trade_data": trade_data
            })
            
            self._logger.log("bull_put_spread_executed", trade_data)
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _execute_bear_call_spread(self, ticker: str, underlying_price: float, 
                                 max_daily_loss: float) -> Dict[str, Any]:
        """Execute bear call spread strategy"""
        
        result = {"success": False, "error": None, "expected_profit": 0, "risk": 0}
        
        try:
            # Similar to bull put spread but with calls
            options_chain = self._generate_realistic_options_chain(ticker, underlying_price, "call")
            if not options_chain:
                result["error"] = "No options chain available"
                return result
            
            config = self.strategy_configs[OptionStrategy.BEAR_CALL_SPREAD]
            spread = self._find_optimal_vertical_spread(options_chain, config, underlying_price)
            
            if not spread:
                result["error"] = "No suitable spread found"
                return result
            
            short_call, long_call = spread
            credit = short_call["bid"] - long_call["ask"]
            
            # For demo: simulate with underlying short position
            underlying_order = self._alpaca.place_market_order(
                symbol=ticker,
                side="sell",  # Bearish bias
                notional=min(25.0, max_daily_loss * 0.3)
            )
            
            result.update({
                "success": True,
                "expected_profit": credit * 100 * config["profit_target"],  # Assuming 1 contract
                "risk": (long_call["strike"] - short_call["strike"] - credit) * 100
            })
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _execute_iron_condor(self, ticker: str, underlying_price: float, 
                           max_daily_loss: float) -> Dict[str, Any]:
        """Execute iron condor strategy"""
        
        result = {"success": False, "error": None, "expected_profit": 0, "risk": 0}
        
        try:
            # Iron condor = Bull put spread + Bear call spread
            # For demo: simulate with neutral underlying position (no trade)
            
            config = self.strategy_configs[OptionStrategy.IRON_CONDOR]
            expected_credit = 1.5  # Simulate $1.50 credit
            expected_profit = expected_credit * 100 * config["profit_target"]
            
            result.update({
                "success": True,
                "expected_profit": expected_profit,
                "risk": (5 * 100) - (expected_credit * 100)  # Assume 5-wide spreads
            })
            
            self._logger.log("iron_condor_simulated", {
                "ticker": ticker,
                "expected_profit": expected_profit,
                "note": "Strategy simulated - real implementation needed"
            })
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _execute_straddle(self, ticker: str, underlying_price: float, 
                         max_daily_loss: float) -> Dict[str, Any]:
        """Execute long straddle strategy"""
        
        result = {"success": False, "error": None, "expected_profit": 0, "risk": 0}
        
        try:
            # Long straddle = Long call + Long put at same strike
            # For demo: simulate with larger underlying position (expecting big move)
            
            underlying_order = self._alpaca.place_market_order(
                symbol=ticker,
                side="buy",
                notional=min(40.0, max_daily_loss * 0.4)  # Larger position for vol plays
            )
            
            config = self.strategy_configs[OptionStrategy.STRADDLE]
            estimated_cost = 5.0  # Simulate $5.00 straddle cost
            expected_profit = estimated_cost * 100 * config["profit_target"]
            
            result.update({
                "success": True,
                "expected_profit": expected_profit,
                "risk": estimated_cost * 100
            })
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _generate_realistic_options_chain(self, ticker: str, underlying_price: float, 
                                        option_type: str) -> List[Dict[str, Any]]:
        """Generate realistic options chain with proper Greeks"""
        
        options = []
        
        # Use different expiration dates
        expiry_days = [7, 14, 21, 30, 45, 60]
        
        for dte in expiry_days:
            expiry_date = datetime.now() + timedelta(days=dte)
            
            # Generate strikes around current price
            strike_range = max(10, int(underlying_price * 0.15))  # 15% range
            strike_increment = 1 if underlying_price < 200 else 5
            
            for i in range(-strike_range, strike_range + 1, strike_increment):
                strike = round(underlying_price + i, 2)
                
                # Calculate realistic option pricing
                option_data = self._calculate_option_price(
                    underlying_price, strike, dte, option_type
                )
                
                if option_data:
                    option_data.update({
                        "symbol": f"{ticker}_{expiry_date.strftime('%y%m%d')}{'C' if option_type == 'call' else 'P'}{strike:08.2f}",
                        "type": option_type,
                        "strike": strike,
                        "expiry": expiry_date,
                        "dte": dte
                    })
                    options.append(option_data)
        
        return options
    
    def _calculate_option_price(self, spot: float, strike: float, dte: int, 
                               option_type: str) -> Dict[str, Any]:
        """Calculate realistic option price with Greeks"""
        
        # Simplified Black-Scholes approximation
        time_to_expiry = dte / 365.0
        risk_free_rate = 0.05
        volatility = 0.25  # 25% annual volatility
        
        # Calculate d1 and d2
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
        d2 = d1 - volatility * math.sqrt(time_to_expiry)
        
        # Cumulative normal distribution approximation
        def norm_cdf(x):
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        if option_type == "call":
            price = spot * norm_cdf(d1) - strike * math.exp(-risk_free_rate * time_to_expiry) * norm_cdf(d2)
            delta = norm_cdf(d1)
        else:  # put
            price = strike * math.exp(-risk_free_rate * time_to_expiry) * norm_cdf(-d2) - spot * norm_cdf(-d1)
            delta = -norm_cdf(-d1)
        
        # Add bid/ask spread
        spread = max(0.05, price * 0.03)
        
        return {
            "bid": max(0.01, price - spread/2),
            "ask": max(0.02, price + spread/2),
            "delta": delta,
            "volume": random.randint(50, 1000),
            "open_interest": random.randint(100, 5000)
        }
    
    def _find_optimal_vertical_spread(self, options_chain: List[Dict], config: Dict, 
                                    underlying_price: float) -> Optional[Tuple[Dict, Dict]]:
        """Find optimal vertical spread based on strategy config"""
        
        # Filter options by DTE
        filtered_options = [
            opt for opt in options_chain 
            if config["min_dte"] <= opt["dte"] <= config["max_dte"]
        ]
        
        best_spread = None
        best_score = 0
        
        for short_option in filtered_options:
            # Check if short option meets delta criteria
            short_delta_range = config["short_delta_range"]
            if isinstance(short_delta_range[0], tuple):  # Iron condor case
                continue
                
            if not (short_delta_range[0] <= short_option["delta"] <= short_delta_range[1]):
                continue
            
            for long_option in filtered_options:
                # Check if long option meets delta criteria
                long_delta_range = config["long_delta_range"]
                if not (long_delta_range[0] <= long_option["delta"] <= long_delta_range[1]):
                    continue
                
                # Ensure proper spread structure
                if short_option["type"] == "put":
                    if long_option["strike"] >= short_option["strike"]:
                        continue
                else:  # call
                    if long_option["strike"] <= short_option["strike"]:
                        continue
                
                # Same expiration
                if short_option["dte"] != long_option["dte"]:
                    continue
                
                spread_width = abs(short_option["strike"] - long_option["strike"])
                credit = short_option["bid"] - long_option["ask"]
                
                # Check spread width and credit constraints
                if not (config["spread_width_range"][0] <= spread_width <= config["spread_width_range"][1]):
                    continue
                
                if not (config["min_credit"] <= credit <= config["max_credit"]):
                    continue
                
                # Score the spread
                credit_score = credit / config["max_credit"]
                width_score = 1 - (spread_width - config["spread_width_range"][0]) / (config["spread_width_range"][1] - config["spread_width_range"][0])
                liquidity_score = min(short_option["volume"], long_option["volume"]) / 1000
                
                total_score = credit_score * 0.5 + width_score * 0.3 + liquidity_score * 0.2
                
                if total_score > best_score:
                    best_score = total_score
                    best_spread = (short_option, long_option)
        
        return best_spread
    
    def _is_options_position(self, position) -> bool:
        """Check if position is an options contract"""
        return len(position.symbol) > 6 and any(ticker in position.symbol for ticker in self.tickers)
    
    def _manage_options_position(self, position):
        """Enhanced position management with strategy-specific rules"""
        
        try:
            # Get trade data
            trade_data = self._get_trade_data_for_position(position)
            
            if trade_data:
                self._manage_strategy_position(position, trade_data)
            else:
                self._basic_position_management(position)
                
        except Exception as e:
            self._logger.error(f"Position management failed for {position.symbol}: {e}")
    
    def _manage_strategy_position(self, position, trade_data: Dict):
        """Manage position based on original strategy"""
        
        strategy = trade_data.get("strategy", "unknown")
        current_pnl_pct = (position.unrealized_pl / abs(position.market_value)) * 100 if position.market_value != 0 else 0
        
        # Strategy-specific exit rules
        if strategy == "bull_put_spread":
            profit_target = 50  # 50% of credit
            stop_loss = -200   # 200% of credit (max loss)
        elif strategy == "iron_condor":
            profit_target = 25  # 25% of credit
            stop_loss = -250   # More conservative
        else:
            profit_target = 40
            stop_loss = -100
        
        # Check exit conditions
        should_close = False
        reason = ""
        
        if current_pnl_pct >= profit_target:
            should_close = True
            reason = "profit_target"
        elif current_pnl_pct <= stop_loss:
            should_close = True
            reason = "stop_loss"
        elif datetime.now().time() >= time(15, 45):  # 15 minutes before close
            should_close = True
            reason = "end_of_day"
        
        if should_close:
            self._close_position(position, reason)
    
    def _basic_position_management(self, position):
        """Basic position management fallback"""
        
        try:
            pnl_pct = (position.unrealized_pl / abs(position.market_value)) * 100 if position.market_value != 0 else 0
            
            if pnl_pct >= 40:  # 40% profit
                self._close_position(position, "profit_target_basic")
            elif pnl_pct <= -50:  # 50% loss
                self._close_position(position, "stop_loss_basic")
            elif datetime.now().time() >= time(15, 45):
                self._close_position(position, "end_of_day_basic")
                
        except Exception as e:
            self._logger.error(f"Basic position management failed: {e}")
    
    def _get_trade_data_for_position(self, position) -> Optional[Dict]:
        """Get stored trade data for position"""
        
        try:
            state_data = get_state()
            for key, value in state_data.items():
                if key.startswith(f"options_trades.{self.bot_id}") and isinstance(value, dict):
                    if value.get("order_id") == getattr(position, 'id', None):
                        return value
            return None
        except:
            return None
    
    def _close_position(self, position, reason: str):
        """Close position with detailed logging"""
        
        try:
            side = "sell" if position.side == "long" else "buy"
            qty = abs(float(position.qty))
            
            order_response = self._alpaca.place_market_order(
                symbol=position.symbol,
                side=side,
                qty=qty
            )
            
            self._logger.log("options_position_closed", {
                "symbol": position.symbol,
                "side": side,
                "qty": qty,
                "reason": reason,
                "pnl": position.unrealized_pl,
                "order_id": order_response.get("id"),
                "bot_id": self.bot_id
            })
            
        except Exception as e:
            self._logger.error(f"Failed to close position {position.symbol}: {e}")
