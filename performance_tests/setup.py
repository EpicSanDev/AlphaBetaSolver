#!/usr/bin/env python3
"""
Setup script for performance test dependencies
"""

import subprocess
import sys
import os
from pathlib import Path

def install_requirements():
    """Install required packages for performance tests"""
    
    requirements = [
        "matplotlib>=3.5.0",
        "numpy>=1.21.0",
        "psutil>=5.8.0",
        "aiohttp>=3.8.0",
        "requests>=2.25.0"
    ]
    
    print("Installing performance test dependencies...")
    
    for package in requirements:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError as e:
            print(f"Failed to install {package}: {e}")
            return False
    
    print("✅ All dependencies installed successfully!")
    return True

def create_results_directories():
    """Create necessary result directories"""
    
    base_dir = Path(__file__).parent
    
    directories = [
        base_dir / "results",
        base_dir / "load_test_results", 
        base_dir / "validation_results"
    ]
    
    for directory in directories:
        directory.mkdir(exist_ok=True)
        print(f"Created directory: {directory}")

def main():
    """Main setup function"""
    
    print("Setting up AlphaBetaSolver Performance Test Environment")
    print("=" * 60)
    
    # Install dependencies
    if not install_requirements():
        return 1
    
    # Create directories
    create_results_directories()
    
    print("\n✅ Performance test environment setup completed!")
    print("\nYou can now run:")
    print("  python cfr_performance_analyzer.py   # CFR algorithm performance analysis")
    print("  python load_tester.py               # Distributed system load testing")  
    print("  python gto_validator.py             # GTO strategy validation")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
