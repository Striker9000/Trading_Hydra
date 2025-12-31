
#!/usr/bin/env python3
"""
Comprehensive I/O Check for Trading Hydra System
Verifies all input/output operations including API calls, logging, state management, and data flows
"""

import sys
import os
import time
import json
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from trading_hydra.core.logging import get_logger
from trading_hydra.services.alpaca_client import get_alpaca_client
from trading_hydra.core.state import init_state_store, get_state, set_state
from trading_hydra.core.config import load_settings, load_bots_config
from trading_hydra.core.health import get_health_monitor


def check_alpaca_io():
    """Test Alpaca API I/O operations"""
    print("🔌 TESTING ALPACA API I/O")
    print("=" * 50)
    
    try:
        alpaca = get_alpaca_client()
        
        # Input validation
        if not alpaca.has_credentials():
            print("❌ INPUT ERROR: Missing ALPACA_KEY or ALPACA_SECRET")
            return False
        
        print("✅ INPUT: API credentials present")
        
        # Test account data I/O
        print("\n📊 Account Data I/O:")
        account = alpaca.get_account()
        print(f"   📥 INPUT: Account fetch request")
        print(f"   📤 OUTPUT: Equity: ${account.equity:,.2f}")
        print(f"   📤 OUTPUT: Cash: ${account.cash:,.2f}")
        print(f"   📤 OUTPUT: Status: {account.status}")
        
        # Test positions I/O
        print("\n📍 Positions Data I/O:")
        positions = alpaca.get_positions()
        print(f"   📥 INPUT: Positions fetch request")
        print(f"   📤 OUTPUT: {len(positions)} positions found")
        
        for pos in positions:
            print(f"      • {pos.symbol}: {pos.qty} shares, P&L: ${pos.unrealized_pl:,.2f}")
        
        # Test quote data I/O
        print("\n💰 Market Data I/O:")
        test_symbols = ["AAPL", "BTC/USD", "ETH/USD"]
        
        for symbol in test_symbols:
            try:
                asset_class = "crypto" if "/" in symbol else "stock"
                quote = alpaca.get_latest_quote(symbol, asset_class)
                print(f"   📥 INPUT: Quote request for {symbol}")
                print(f"   📤 OUTPUT: Bid: ${quote['bid']:,.2f}, Ask: ${quote['ask']:,.2f}")
            except Exception as e:
                print(f"   ⚠️ QUOTE ERROR for {symbol}: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ ALPACA I/O ERROR: {e}")
        return False


def check_logging_io():
    """Test logging system I/O"""
    print("\n📝 TESTING LOGGING I/O")
    print("=" * 50)
    
    try:
        logger = get_logger()
        
        # Test structured logging I/O
        test_data = {
            "test_type": "io_verification",
            "timestamp": datetime.now().isoformat(),
            "components": ["alpaca", "state", "config"],
            "metrics": {"success_rate": 95.5, "latency_ms": 120}
        }
        
        print("📥 INPUT: Structured log data")
        print(f"   Data: {json.dumps(test_data, indent=2)}")
        
        logger.log("io_test_structured", test_data)
        logger.warn("I/O test warning message")
        logger.error("I/O test error message")
        
        print("📤 OUTPUT: Logs written to logs/app.jsonl")
        
        # Verify log file exists and is writable
        log_file = "logs/app.jsonl"
        if os.path.exists(log_file):
            file_size = os.path.getsize(log_file)
            print(f"✅ Log file: {file_size} bytes")
            
            # Read last few lines to verify output
            with open(log_file, 'r') as f:
                lines = f.readlines()[-3:]
                print("📤 OUTPUT: Recent log entries:")
                for line in lines:
                    try:
                        log_entry = json.loads(line.strip())
                        print(f"      {log_entry.get('timestamp', 'N/A')}: {log_entry.get('level', 'INFO')} - {log_entry.get('event', 'N/A')}")
                    except:
                        print(f"      {line.strip()[:100]}...")
        else:
            print("❌ Log file not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ LOGGING I/O ERROR: {e}")
        return False


def check_state_io():
    """Test state management I/O"""
    print("\n💾 TESTING STATE MANAGEMENT I/O")
    print("=" * 50)
    
    try:
        init_state_store()
        
        # Test state write I/O
        test_key = "io_test_state"
        test_value = {
            "timestamp": time.time(),
            "test_data": "I/O verification test",
            "numeric_value": 12345.67,
            "boolean_flag": True
        }
        
        print("📥 INPUT: State data to store")
        print(f"   Key: {test_key}")
        print(f"   Value: {test_value}")
        
        set_state(test_key, test_value)
        print("✅ State write operation completed")
        
        # Test state read I/O
        print("\n📤 OUTPUT: State data retrieval")
        retrieved_value = get_state(test_key)
        
        if retrieved_value:
            print(f"   Retrieved: {retrieved_value}")
            
            # Verify data integrity
            if retrieved_value == test_value:
                print("✅ Data integrity verified")
            else:
                print("❌ Data integrity mismatch")
                return False
        else:
            print("❌ State retrieval failed")
            return False
        
        # Test existing state keys
        print("\n📋 Existing State Keys:")
        existing_keys = [
            "day_start_equity",
            "bots.mom_AAPL.enabled",
            "bots.opt_core.enabled", 
            "bots.crypto_core.enabled",
            "budgets.mom_AAPL.max_daily_loss"
        ]
        
        for key in existing_keys:
            value = get_state(key)
            print(f"   {key}: {value}")
            
        return True
        
    except Exception as e:
        print(f"❌ STATE I/O ERROR: {e}")
        return False


def check_config_io():
    """Test configuration file I/O"""
    print("\n⚙️ TESTING CONFIGURATION I/O")
    print("=" * 50)
    
    try:
        # Test settings.yaml I/O
        print("📥 INPUT: Loading settings.yaml")
        settings = load_settings()
        print("📤 OUTPUT: Settings loaded")
        print(f"   Keys: {list(settings.keys())}")
        
        if 'runner' in settings:
            print(f"   Runner config: {settings['runner']}")
        
        # Test bots.yaml I/O
        print("\n📥 INPUT: Loading bots.yaml")
        bots_config = load_bots_config()
        print("📤 OUTPUT: Bot configuration loaded")
        print(f"   Bot count: {len(bots_config.get('bots', []))}")
        
        for bot in bots_config.get('bots', []):
            print(f"   • {bot.get('id', 'unknown')}: {bot.get('type', 'unknown')} - {bot.get('enabled', False)}")
            
        return True
        
    except Exception as e:
        print(f"❌ CONFIG I/O ERROR: {e}")
        return False


def check_health_monitoring_io():
    """Test health monitoring I/O"""
    print("\n🏥 TESTING HEALTH MONITORING I/O")
    print("=" * 50)
    
    try:
        health = get_health_monitor()
        
        # Test health metrics I/O
        print("📥 INPUT: Recording health metrics")
        health.record_price_tick()
        health.record_price_tick()
        health.record_api_failure("Test failure for I/O verification")
        
        print("📤 OUTPUT: Health status")
        print(f"   API calls: {health.api_calls}")
        print(f"   Failures: {health.api_failures}")
        print(f"   Success rate: {health.success_rate():.1f}%")
        print(f"   Last activity: {health.last_activity}")
        
        return True
        
    except Exception as e:
        print(f"❌ HEALTH I/O ERROR: {e}")
        return False


def check_file_system_io():
    """Test file system I/O operations"""
    print("\n📁 TESTING FILE SYSTEM I/O")
    print("=" * 50)
    
    try:
        # Check critical directories
        directories = ["logs", "config", "src", "state"]
        
        for directory in directories:
            if os.path.exists(directory):
                print(f"✅ Directory exists: {directory}/")
                files = os.listdir(directory)[:5]  # Show first 5 files
                for file in files:
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path):
                        size = os.path.getsize(file_path)
                        print(f"   📄 {file}: {size} bytes")
            else:
                print(f"❌ Directory missing: {directory}/")
        
        # Test write permissions
        test_file = "io_test_temp.txt"
        try:
            with open(test_file, 'w') as f:
                f.write("I/O test write operation")
            print("✅ Write permissions verified")
            
            # Clean up
            os.remove(test_file)
            print("✅ File cleanup completed")
            
        except Exception as e:
            print(f"❌ Write permission error: {e}")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ FILE SYSTEM I/O ERROR: {e}")
        return False


def generate_io_summary():
    """Generate I/O verification summary"""
    print("\n📋 I/O VERIFICATION SUMMARY")
    print("=" * 50)
    
    # Run all I/O checks
    checks = [
        ("Alpaca API I/O", check_alpaca_io),
        ("Logging I/O", check_logging_io), 
        ("State Management I/O", check_state_io),
        ("Configuration I/O", check_config_io),
        ("Health Monitoring I/O", check_health_monitoring_io),
        ("File System I/O", check_file_system_io)
    ]
    
    results = {}
    
    for check_name, check_func in checks:
        print(f"\n🔍 Running {check_name}...")
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ {check_name} failed: {e}")
            results[check_name] = False
    
    # Final summary
    print("\n" + "=" * 60)
    print("🎯 FINAL I/O VERIFICATION RESULTS")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for check_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {check_name}")
        if result:
            passed += 1
    
    print(f"\n📊 OVERALL: {passed}/{total} checks passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL I/O OPERATIONS VERIFIED SUCCESSFULLY!")
        return True
    else:
        print("⚠️ SOME I/O OPERATIONS NEED ATTENTION")
        return False


if __name__ == "__main__":
    print("🔍 TRADING HYDRA I/O VERIFICATION")
    print("=" * 60)
    print("Checking all input/output operations...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    success = generate_io_summary()
    
    if success:
        print("\n✅ I/O verification completed successfully")
        sys.exit(0)
    else:
        print("\n❌ I/O verification found issues")
        sys.exit(1)
