
#!/usr/bin/env python3
"""
Alpaca Connection Reset Script
Safely disconnects and reconnects to Alpaca API with fresh credentials
"""

import sys
import os
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from trading_hydra.core.logging import get_logger
from trading_hydra.services.alpaca_client import get_alpaca_client
from trading_hydra.core.health import get_health_monitor

def disconnect_alpaca():
    """Safely disconnect from Alpaca API"""
    logger = get_logger()
    print("🔌 DISCONNECTING FROM ALPACA...")
    
    try:
        # Clear any existing client instance
        import trading_hydra.services.alpaca_client as alpaca_module
        if hasattr(alpaca_module, '_alpaca_client'):
            alpaca_module._alpaca_client = None
            logger.log("alpaca_disconnect", {"action": "cleared_client_instance"})
        
        # Reset health monitor
        health = get_health_monitor()
        health.reset_counters()
        
        print("✅ Disconnected successfully")
        logger.log("alpaca_disconnect_complete", {"timestamp": time.time()})
        return True
        
    except Exception as e:
        print(f"❌ Disconnect error: {e}")
        logger.error(f"Disconnect failed: {e}")
        return False

def reconnect_alpaca():
    """Reconnect to Alpaca API with fresh credentials"""
    logger = get_logger()
    print("🔗 RECONNECTING TO ALPACA...")
    
    try:
        # Force creation of new client instance
        client = get_alpaca_client()
        
        if not client.has_credentials():
            print("❌ CRITICAL: Missing ALPACA_KEY or ALPACA_SECRET")
            print("Please verify your credentials in the Secrets tab")
            return False
        
        # Test the new connection
        print("🧪 Testing new connection...")
        account = client.get_account()
        
        print("✅ Reconnected successfully!")
        print(f"   Account Status: {account.status}")
        print(f"   Total Equity: ${account.equity:,.2f}")
        print(f"   Environment: {'Paper Trading' if client.is_paper else 'Live Trading'}")
        
        logger.log("alpaca_reconnect_complete", {
            "equity": account.equity,
            "status": account.status,
            "paper_trading": client.is_paper,
            "timestamp": time.time()
        })
        
        return True
        
    except Exception as e:
        print(f"❌ Reconnect error: {e}")
        logger.error(f"Reconnect failed: {e}")
        return False

def refresh_connection():
    """Complete connection refresh cycle"""
    logger = get_logger()
    print("🔄 ALPACA CONNECTION REFRESH")
    print("=" * 40)
    
    logger.log("connection_refresh_start", {"timestamp": time.time()})
    
    # Step 1: Disconnect
    if not disconnect_alpaca():
        print("\n🚨 REFRESH FAILED - Disconnect error")
        return False
    
    # Brief pause to ensure clean disconnect
    print("⏳ Waiting 2 seconds...")
    time.sleep(2)
    
    # Step 2: Reconnect
    if not reconnect_alpaca():
        print("\n🚨 REFRESH FAILED - Reconnect error")
        return False
    
    print("\n🎉 CONNECTION REFRESH COMPLETE")
    logger.log("connection_refresh_success", {"timestamp": time.time()})
    return True

if __name__ == "__main__":
    print("Starting Alpaca connection refresh...")
    
    success = refresh_connection()
    
    if not success:
        print("\n❌ CONNECTION REFRESH FAILED")
        print("Troubleshooting steps:")
        print("1. Check ALPACA_KEY and ALPACA_SECRET in Secrets tab")
        print("2. Verify Alpaca account status")
        print("3. Check internet connectivity")
        sys.exit(1)
    else:
        print("\n✅ Ready for trading operations")
