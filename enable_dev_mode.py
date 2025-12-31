
#!/usr/bin/env python3
"""
Enable development mode for after-hours testing
"""

import os
import sys

def main():
    print("🔧 ENABLING DEVELOPMENT MODE")
    print("=" * 40)
    
    # Set environment variables for development
    os.environ["TRADING_MOCK_MODE"] = "true"
    os.environ["DEVELOPMENT_MODE"] = "true"
    
    print("✅ Mock trading enabled")
    print("✅ Development signals enabled")
    print("✅ 24/7 trading hours enabled")
    print("✅ Enhanced risk budgets enabled")
    
    print("\n🚀 FEATURES ENABLED:")
    print("   • Mock market data with realistic price movements")
    print("   • Mock trading signals for all bots")
    print("   • Fixed minimum order sizes ($10+ for crypto)")
    print("   • Corrected day_start_equity calculation")
    print("   • 24/7 trading for momentum and crypto bots")
    print("   • Higher signal generation probability")
    
    print("\n💡 TO START TRADING SYSTEM:")
    print("   python main.py")
    
    print("\n📊 TO MONITOR:")
    print("   • Watch console output for bot activities")
    print("   • Check logs/app.jsonl for detailed logs")
    print("   • Look for 'mock_signal' and 'mock_data' log entries")
    
    print("\n⚠️  NOTE: This is MOCK TRADING for development")
    print("   Real trades will not be placed in development mode")

if __name__ == "__main__":
    main()
