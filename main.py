import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from runner.main import main as run_trading_system

def main():
    print("Starting Trading Hydra System...")
    try:
        run_trading_system()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"System error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
