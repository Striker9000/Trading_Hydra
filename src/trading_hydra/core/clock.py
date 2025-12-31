"""Market clock utilities with timezone support"""
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Optional

from .config import load_settings


class MarketClock:
    def __init__(self, timezone: Optional[str] = None):
        if timezone:
            self.tz = ZoneInfo(timezone)
        else:
            settings = load_settings()
            tz_name = settings.get("system", {}).get("timezone", "America/New_York")
            self.tz = ZoneInfo(tz_name)
    
    def now(self) -> datetime:
        return datetime.now(self.tz)
    
    def get_date_string(self) -> str:
        return self.now().strftime("%Y-%m-%d")
    
    def is_market_hours(self) -> bool:
        now = self.now()
        if now.weekday() >= 5:
            return False
        
        market_open = time(9, 30)
        market_close = time(16, 0)
        current_time = now.time()
        
        return market_open <= current_time <= market_close
    
    def is_extended_hours(self) -> bool:
        now = self.now()
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        pre_market_open = time(4, 0)
        after_hours_close = time(20, 0)
        
        return pre_market_open <= current_time <= after_hours_close


_market_clock: Optional[MarketClock] = None


def get_market_clock() -> MarketClock:
    global _market_clock
    if _market_clock is None:
        _market_clock = MarketClock()
    return _market_clock
