
#!/usr/bin/env python3
"""
Account Balance Verification Script
Checks Alpaca account details and compares with expected values
"""

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from trading_hydra.core.logging import get_logger
from trading_hydra.services.alpaca_client import get_alpaca_client
from trading_hydra.core.health import get_health_monitor

def verify_account_balance():
    """Comprehensive account balance verification"""
    logger = get_logger()
    print("🔍 ACCOUNT BALANCE VERIFICATION")
    print("=" * 50)
    
    try:
        client = get_alpaca_client()
        
        # Check credentials
        if not client.has_credentials():
            print("❌ CRITICAL: Missing ALPACA_KEY or ALPACA_SECRET")
            print("Please verify your credentials in the Secrets tab")
            return False
        
        print(f"✅ API Credentials: Present")
        print(f"✅ Environment: {'Paper Trading' if client.is_paper else 'Live Trading'}")
        print(f"✅ Base URL: {client.base_url}")
        print()
        
        # Get account details
        print("📊 FETCHING ACCOUNT DATA...")
        account = client.get_account()
        
        print("💰 CURRENT ACCOUNT STATUS:")
        print(f"   Account Status: {account.status}")
        print(f"   Total Equity: ${account.equity:,.2f}")
        print(f"   Cash Available: ${account.cash:,.2f}")
        print(f"   Buying Power: ${account.buying_power:,.2f}")
        print()
        
        # Compare with expected value
        expected_equity = 44662.70
        actual_equity = account.equity
        difference = actual_equity - expected_equity
        
        print("🎯 BALANCE COMPARISON:")
        print(f"   Expected Equity: ${expected_equity:,.2f}")
        print(f"   Actual Equity: ${actual_equity:,.2f}")
        print(f"   Difference: ${difference:,.2f}")
        
        if abs(difference) > 100:  # Allow for small fluctuations
            print(f"⚠️  MAJOR DISCREPANCY DETECTED!")
            if actual_equity < expected_equity:
                print(f"   Account shows ${abs(difference):,.2f} LESS than expected")
            else:
                print(f"   Account shows ${abs(difference):,.2f} MORE than expected")
        else:
            print(f"✅ Balance within acceptable range")
        
        print()
        
        # Get positions
        print("📈 CHECKING POSITIONS...")
        positions = client.get_positions()
        
        if positions:
            total_position_value = sum(p.market_value for p in positions)
            print(f"   Active Positions: {len(positions)}")
            print(f"   Total Position Value: ${total_position_value:,.2f}")
            print("   Position Details:")
            for pos in positions:
                print(f"      {pos.symbol}: {pos.qty} shares @ ${pos.market_value:,.2f} (P&L: ${pos.unrealized_pl:,.2f})")
        else:
            print("   No active positions")
        
        print()
        
        # Account type verification
        print("🔍 ACCOUNT VERIFICATION:")
        if client.is_paper:
            print("   ⚠️  This is a PAPER TRADING account")
            print("   Real money values should be checked in LIVE account")
            if expected_equity > 1000:
                print("   💡 High expected value suggests you might want LIVE account")
        else:
            print("   💰 This is a LIVE TRADING account")
            print("   Values shown represent real money")
        
        # Trading capability check
        print()
        print("⚡ TRADING CAPABILITY:")
        if account.buying_power < 1:
            print("   ❌ Insufficient buying power for meaningful trades")
            print(f"   Current: ${account.buying_power:,.2f}")
            print("   Minimum recommended: $1000+ for options trading")
        elif account.buying_power < 1000:
            print("   ⚠️  Limited buying power")
            print(f"   Current: ${account.buying_power:,.2f}")
            print("   May limit options trading strategies")
        else:
            print("   ✅ Sufficient buying power for trading")
        
        return True
        
    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        logger.error(f"Account verification error: {e}")
        return False

if __name__ == "__main__":
    print("Starting account balance verification...")
    success = verify_account_balance()
    
    if not success:
        print("\n🚨 VERIFICATION FAILED")
        print("Please check:")
        print("1. Alpaca API credentials (ALPACA_KEY, ALPACA_SECRET)")
        print("2. Internet connection")
        print("3. Alpaca account status")
        sys.exit(1)
    else:
        print("\n✅ VERIFICATION COMPLETE")
        print("Check the results above for any discrepancies")
