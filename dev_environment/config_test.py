"""
Test environment configuration
This file contains settings specific to the test environment
"""

import os
from config import *  # Import all settings from main config

# Override settings for test environment
TEST_MODE = True
TEST_ENVIRONMENT = True

# Display test mode banner on startup
print("\n" + "="*50)
print("🧪 RUNNING IN TEST ENVIRONMENT 🧪")
print("Signals will be processed but not sent to MT5 terminals")
print("="*50 + "\n")

# Modify MT5 assets for testing if needed
# Example: Use a limited set of assets for testing
# MT5_ASSETS = ["EURUSD", "GBPUSD", "XAUUSD"]  # Uncomment to override

# Override functions as needed
def oanda_to_mt5(symbol):
    """Override symbol conversion to add test prefix if needed"""
    # Convert normally first
    mt5_symbol = symbol.replace("_", "") if "_" in symbol else symbol
    
    # Add a "TEST_" prefix for special test handling (optional)
    # mt5_symbol = "TEST_" + mt5_symbol  # Uncomment to add prefix
    
    # Log the conversion
    print(f"[TEST ENV] Symbol conversion: {symbol} -> {mt5_symbol}")
    return mt5_symbol