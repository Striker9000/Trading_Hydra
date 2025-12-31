"""Alpaca API client for trading operations"""
import os
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import requests
from decimal import Decimal, ROUND_HALF_UP

from ..core.logging import get_logger
from ..core.health import get_health_monitor
from .mock_data import get_mock_provider, is_development_mode

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, GetOrdersRequest
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, AssetClass
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient, OptionHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest, CryptoLatestQuoteRequest
    ALPACA_SDK_AVAILABLE = True
except ImportError:
    print("Warning: alpaca-py not installed. Using fallback HTTP client.")
    ALPACA_SDK_AVAILABLE = False


@dataclass
class AlpacaAccount:
    equity: float
    cash: float
    buying_power: float
    status: str


@dataclass
class AlpacaPosition:
    symbol: str
    qty: float
    market_value: float
    unrealized_pl: float
    side: str


class AlpacaClient:
    def __init__(self):
        self.api_key = os.environ.get("ALPACA_KEY")
        self.api_secret = os.environ.get("ALPACA_SECRET")
        self.is_paper = os.environ.get("ALPACA_PAPER", "true").lower() != "false"

        self.base_url = (
            "https://paper-api.alpaca.markets" if self.is_paper
            else "https://api.alpaca.markets"
        )

        self._logger = get_logger()
        self._health = get_health_monitor()

        # Initialize Alpaca SDK clients
        if ALPACA_SDK_AVAILABLE and self.has_credentials():
            self._trading_client = TradingClient(
                api_key=self.api_key,
                secret_key=self.api_secret,
                paper=self.is_paper
            )
            self._stock_data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.api_secret
            )
            self._crypto_data_client = CryptoHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.api_secret
            )
        else:
            self._trading_client = None
            self._stock_data_client = None
            self._crypto_data_client = None

    def _headers(self) -> Dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.api_key or "",
            "APCA-API-SECRET-KEY": self.api_secret or "",
        }

    def has_credentials(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        retries: int = 2
    ) -> Dict[str, Any]:
        if not self.has_credentials():
            raise RuntimeError("ALPACA_KEY and ALPACA_SECRET required")

        url = f"{self.base_url}{endpoint}"

        for attempt in range(retries + 1):
            try:
                resp = requests.request(
                    method, 
                    url, 
                    headers=self._headers(),
                    json=data if method != "GET" else None,
                    params=data if method == "GET" else None,
                    timeout=30
                )

                if resp.status_code >= 400:
                    error_text = resp.text
                    self._health.record_api_failure(f"{resp.status_code}: {error_text}")
                    raise RuntimeError(f"Alpaca API error {resp.status_code}: {error_text}")

                self._health.record_price_tick()

                if resp.status_code == 204:
                    return {}
                return resp.json()

            except requests.RequestException as e:
                self._health.record_api_failure(str(e))
                if attempt < retries:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise RuntimeError(f"Alpaca request failed: {e}")

        raise RuntimeError("Alpaca request failed after retries")

    def get_account(self) -> AlpacaAccount:
        self._logger.log("alpaca_get_account", {})
        data = self._request("GET", "/v2/account")

        # Validate API response structure
        required_fields = ["equity", "cash", "buying_power", "status"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field '{field}' in Alpaca account response")

        # Validate and convert numeric fields
        try:
            equity = float(data["equity"])
            cash = float(data["cash"]) 
            buying_power = float(data["buying_power"])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid numeric data in Alpaca account response: {e}")

        # Validate equity is reasonable
        if equity < 0:
            raise ValueError(f"Invalid negative equity: {equity}")

        status = str(data["status"])
        if status not in ["ACTIVE", "ACCOUNT_CLOSED", "ACCOUNT_FROZEN", "PENDING_APPROVAL"]:
            self._logger.warn(f"Unknown account status: {status}")

        account = AlpacaAccount(
            equity=equity,
            cash=cash,
            buying_power=buying_power,
            status=status
        )

        self._logger.log("alpaca_account", {
            "equity": account.equity,
            "cash": account.cash,
            "status": account.status,
            "validated": True
        })

        return account

    def get_positions(self) -> List[AlpacaPosition]:
        self._logger.log("alpaca_get_positions", {})

        # Use mock data during development/after hours
        if is_development_mode():
            mock_provider = get_mock_provider()
            mock_positions_data = mock_provider.get_mock_positions()

            positions = []
            for p in mock_positions_data:
                positions.append(AlpacaPosition(
                    symbol=p["symbol"],
                    qty=float(p["qty"]),
                    market_value=p["market_value"],
                    unrealized_pl=p["unrealized_pl"],
                    side=p["side"]
                ))

            self._logger.log("alpaca_positions", {
                "count": len(positions),
                "symbols": [p.symbol for p in positions],
                "total_value": sum(p.market_value for p in positions),
                "validated": True,
                "mock_data": True
            })
            return positions

        data = self._request("GET", "/v2/positions")

        # Validate response is a list
        if not isinstance(data, list):
            raise ValueError("Alpaca positions response must be a list")

        positions = []
        for i, p in enumerate(data):
            if not isinstance(p, dict):
                raise ValueError(f"Position {i} must be a dictionary")

            # Validate required fields
            required_fields = ["symbol", "qty", "market_value", "unrealized_pl", "side"]
            for field in required_fields:
                if field not in p:
                    raise ValueError(f"Missing field '{field}' in position {i}")

            try:
                symbol = str(p["symbol"]).strip().upper()
                qty = float(p["qty"])
                market_value = float(p["market_value"])
                unrealized_pl = float(p["unrealized_pl"])
                side = str(p["side"]).lower()
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid data in position {i}: {e}")

            # Validate symbol
            if not symbol or len(symbol) > 10:
                raise ValueError(f"Invalid symbol in position {i}: '{symbol}'")

            # Validate side
            if side not in ["long", "short"]:
                raise ValueError(f"Invalid side in position {i}: '{side}'")

            positions.append(AlpacaPosition(
                symbol=symbol,
                qty=qty,
                market_value=market_value,
                unrealized_pl=unrealized_pl,
                side=side
            ))

        self._logger.log("alpaca_positions", {
            "count": len(positions),
            "symbols": [p.symbol for p in positions],
            "total_value": sum(p.market_value for p in positions),
            "validated": True
        })
        return positions

    def cancel_all_orders(self) -> int:
        self._logger.log("alpaca_cancel_all_orders", {})
        self._request("DELETE", "/v2/orders")
        self._logger.log("alpaca_orders_cancelled", {})
        return 0

    def close_all_positions(self) -> int:
        self._logger.log("alpaca_close_all_positions", {})
        self._request("DELETE", "/v2/positions")
        self._logger.log("alpaca_positions_closed", {})
        return 0

    def flatten(self) -> Dict[str, Any]:
        self._logger.log("alpaca_flatten_start", {})

        if not self.has_credentials():
            return {"success": False, "error": "No credentials"}

        try:
            self.cancel_all_orders()
            self.close_all_positions()
            self._logger.log("alpaca_flatten_complete", {})
            return {"success": True}
        except Exception as e:
            self._logger.error(f"Flatten failed: {e}")
            return {"success": False, "error": str(e)}

    def _round_notional(self, value: float) -> float:
        """Round notional to 2 decimal places as required by Alpaca API"""
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    def _round_qty(self, value: float) -> float:
        """Round quantity to appropriate decimal places"""
        return float(Decimal(str(value)).quantize(Decimal('0.000000001'), rounding=ROUND_HALF_UP))

    def place_market_order(self, symbol: str, side: str, qty: Optional[float] = None, 
                          notional: Optional[float] = None) -> Dict[str, Any]:
        """Place a market order using the modern SDK"""
        if not self.has_credentials():
            raise RuntimeError("ALPACA_KEY and ALPACA_SECRET required")

        # Clean up notional/qty values
        if notional is not None:
            notional = self._round_notional(notional)
        if qty is not None:
            qty = self._round_qty(qty)

        if ALPACA_SDK_AVAILABLE and self._trading_client:
            try:
                order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

                # Detect crypto pairs and use appropriate time_in_force
                is_crypto = "/" in symbol and "USD" in symbol
                time_in_force = TimeInForce.GTC if is_crypto else TimeInForce.DAY

                if notional is not None:
                    request = MarketOrderRequest(
                        symbol=symbol,
                        side=order_side,
                        time_in_force=time_in_force,
                        notional=notional
                    )
                else:
                    request = MarketOrderRequest(
                        symbol=symbol,
                        side=order_side,
                        time_in_force=time_in_force,
                        qty=qty
                    )

                order = self._trading_client.submit_order(order_data=request)
                self._health.record_price_tick()

                return {
                    "id": str(order.id),
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "qty": str(order.qty) if order.qty else None,
                    "notional": str(order.notional) if order.notional else None,
                    "status": order.status.value,
                    "order_type": order.order_type.value,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
                }

            except Exception as e:
                self._health.record_api_failure(str(e))
                raise RuntimeError(f"SDK Order placement failed: {e}")
        else:
            # Fallback to HTTP requests
            order_data = {
                "symbol": symbol,
                "side": side.lower(),
                "type": "market",
                "time_in_force": "day"
            }

            if notional is not None:
                order_data["notional"] = notional
            else:
                order_data["qty"] = qty

            return self._request("POST", "/v2/orders", order_data)

    def place_limit_order(self, symbol: str, side: str, qty: float, limit_price: float) -> Dict[str, Any]:
        """Place a limit order using the modern SDK"""
        if not self.has_credentials():
            raise RuntimeError("ALPACA_KEY and ALPACA_SECRET required")

        qty = self._round_qty(qty)
        limit_price = self._round_notional(limit_price)

        if ALPACA_SDK_AVAILABLE and self._trading_client:
            try:
                order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL

                request = LimitOrderRequest(
                    symbol=symbol,
                    side=order_side,
                    time_in_force=TimeInForce.DAY,
                    qty=qty,
                    limit_price=limit_price
                )

                order = self._trading_client.submit_order(order_data=request)
                self._health.record_price_tick()

                return {
                    "id": str(order.id),
                    "symbol": order.symbol,
                    "side": order.side.value,
                    "qty": str(order.qty),
                    "limit_price": str(order.limit_price),
                    "status": order.status.value,
                    "order_type": order.order_type.value,
                    "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None
                }

            except Exception as e:
                self._health.record_api_failure(str(e))
                raise RuntimeError(f"SDK Limit order failed: {e}")
        else:
            # Fallback to HTTP requests  
            order_data = {
                "symbol": symbol,
                "side": side.lower(),
                "type": "limit",
                "time_in_force": "day",
                "qty": qty,
                "limit_price": limit_price
            }

            return self._request("POST", "/v2/orders", order_data)

    def get_latest_quote(self, symbol: str, asset_class: str = "stock") -> Dict[str, float]:
        """Get latest bid/ask quote for symbol"""
        self._logger.log("alpaca_get_quote", {"symbol": symbol, "asset_class": asset_class})

        # Use mock data during development/after hours
        if is_development_mode():
            mock_provider = get_mock_provider()
            mock_quote = mock_provider.get_mock_quote(symbol, asset_class)
            self._logger.log("using_mock_quote", {
                "symbol": symbol,
                "mock_bid": mock_quote["bid"],
                "mock_ask": mock_quote["ask"],
                "reason": "development_mode"
            })
            return mock_quote

        try:
            if asset_class == "stock":
                # Use the correct method name for stock quotes
                try:
                    quotes_request = StockLatestQuoteRequest(symbol_or_symbols=[symbol])
                    quotes = self._stock_data_client.get_stock_latest_quote(quotes_request)

                    if symbol in quotes:
                        quote = quotes[symbol]
                        return {
                            "bid": float(quote.bid_price),
                            "ask": float(quote.ask_price),
                            "timestamp": quote.timestamp.isoformat()
                        }
                    else:
                        raise Exception(f"No quote data for {symbol}")
                except AttributeError:
                    # Fallback: try to get latest bar as proxy for quote
                    from alpaca.data.requests import StockBarsRequest
                    from alpaca.data.timeframe import TimeFrame

                    bars_request = StockBarsRequest(
                        symbol_or_symbols=[symbol],
                        timeframe=TimeFrame.Minute,
                        limit=1
                    )
                    bars = self._stock_data_client.get_stock_bars(bars_request)

                    if symbol in bars:
                        bar = bars[symbol][-1] if bars[symbol] else None
                        if bar:
                            # Use close price as both bid and ask (spread approximation)
                            close_price = float(bar.close)
                            return {
                                "bid": close_price * 0.999,  # Slight spread simulation
                                "ask": close_price * 1.001,
                                "timestamp": bar.timestamp.isoformat()
                            }
                    raise Exception(f"No bar data available for {symbol}")

            elif asset_class == "crypto":
                try:
                    from alpaca.data.requests import CryptoLatestQuoteRequest
                    quotes_request = CryptoLatestQuoteRequest(symbol_or_symbols=[symbol])
                    quotes = self._crypto_data_client.get_crypto_latest_quote(quotes_request)

                    if symbol in quotes:
                        quote = quotes[symbol]
                        return {
                            "bid": float(quote.bid_price),
                            "ask": float(quote.ask_price),
                            "timestamp": quote.timestamp.isoformat()
                        }
                    else:
                        raise Exception(f"No crypto quote data for {symbol}")
                except (AttributeError, ImportError):
                    # Fallback: try crypto bars
                    from alpaca.data.requests import CryptoBarsRequest
                    from alpaca.data.timeframe import TimeFrame

                    bars_request = CryptoBarsRequest(
                        symbol_or_symbols=[symbol],
                        timeframe=TimeFrame.Minute,
                        limit=1
                    )
                    bars = self._crypto_data_client.get_crypto_bars(bars_request)

                    if symbol in bars:
                        bar = bars[symbol][-1] if bars[symbol] else None
                        if bar:
                            close_price = float(bar.close)
                            return {
                                "bid": close_price * 0.999,
                                "ask": close_price * 1.001,
                                "timestamp": bar.timestamp.isoformat()
                            }
                    raise Exception(f"No crypto bar data available for {symbol}")
            else:
                raise ValueError(f"Unsupported asset class: {asset_class}")

        except Exception as e:
            error_msg = f"Quote fetch failed for {symbol}: {e}"
            self._logger.warn(error_msg)
            self._health.record_api_failure(str(e))
            # Assuming AlpacaAPIError is defined elsewhere or a base Exception is sufficient
            # For now, let's use a generic Exception if AlpacaAPIError is not defined in this scope
            raise Exception(str(e))


_alpaca_client: Optional[AlpacaClient] = None


def get_alpaca_client() -> AlpacaClient:
    global _alpaca_client
    if _alpaca_client is None:
        _alpaca_client = AlpacaClient()
    return _alpaca_client