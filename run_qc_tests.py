
"""Main QC Test Runner - Execute complete quality control suite"""
import os
import sys
import subprocess

# Ensure we're in the right directory
project_root = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_root)

# Add src to Python path
sys.path.insert(0, os.path.join(project_root, 'src'))

def main():
    print("🚀 TRADING HYDRA QC SUITE LAUNCHER")
    print("=" * 50)
    
    # Change to tests directory
    tests_dir = os.path.join(project_root, 'src', 'trading_hydra', 'tests')
    os.chdir(tests_dir)
    
    try:
        # Run the comprehensive QC suite
        result = subprocess.run([sys.executable, 'run_qc.py'], 
                              capture_output=False, 
                              text=True)
        
        print(f"\n🏁 QC Suite completed with exit code: {result.returncode}")
        
        if result.returncode == 0:
            print("✅ System passed all QC checks - Ready for production!")
        elif result.returncode == 1:
            print("⚠️  System has minor issues but is functional")
        elif result.returncode == 2:
            print("🔴 System has major issues requiring attention")
        else:
            print("❌ QC Suite encountered critical errors")
        
        return result.returncode
        
    except Exception as e:
        print(f"❌ Failed to run QC suite: {e}")
        return 3

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
