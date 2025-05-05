#!/usr/bin/env python3

"""
Configuration module for the MT5 GENESIS EA system

This module provides a single source of truth for configuration values
that are used across the system, such as asset lists and timeframes.
"""

import os

# List of supported assets in OANDA format (with underscore)
# These are mapped to MT5 format (without underscore) in mt5_ea_api.py
ASSETS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "XAU_USD",  # Gold
    "GBP_JPY"
]

# Timeframes for chart generation
TIMEFRAMES = [
    "M5",   # 5 minutes
    "M15",  # 15 minutes
    "M30",  # 30 minutes
    "H1",   # 1 hour
    "H4",   # 4 hours
    "D",    # 1 day
]

# Default timeframe for analysis
DEFAULT_TIMEFRAME = "H1"

# OpenAI Vision API configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Vision API URL and model
VISION_API_URL = "https://api.openai.com/v1/chat/completions"
VISION_MODEL = "gpt-4-vision-preview"

# OANDA API configuration
OANDA_API_KEY = os.environ.get("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.environ.get("OANDA_ACCOUNT_ID", "")

# Define paths for static assets
STATIC_DIR = "static"
CHARTS_DIR = os.path.join(STATIC_DIR, "charts")

# Signal confidence threshold for automatic execution
# Signals with confidence below this threshold will require manual approval
SIGNAL_CONFIDENCE_THRESHOLD = 0.7

# Function to convert OANDA symbol format to MT5 format
def oanda_to_mt5(symbol):
    """Convert OANDA symbol format (with underscore) to MT5 format (without underscore)
    
    Args:
        symbol (str): Symbol in OANDA format (e.g., "EUR_USD")
        
    Returns:
        str: Symbol in MT5 format (e.g., "EURUSD")
    """
    return symbol.replace("_", "") if symbol else ""

# Function to convert MT5 symbol format to OANDA format
def mt5_to_oanda(symbol):
    """Convert MT5 symbol format (without underscore) to OANDA format (with underscore)
    
    Args:
        symbol (str): Symbol in MT5 format (e.g., "EURUSD")
        
    Returns:
        str: Symbol in OANDA format (e.g., "EUR_USD")
    """
    if not symbol:
        return ""
        
    # Special case for gold
    if symbol == "XAUUSD":
        return "XAU_USD"
    
    # Regular currency pairs (assuming 6-character format)
    if len(symbol) == 6:
        return f"{symbol[:3]}_{symbol[3:]}"
    
    # If not a standard format, return as-is
    return symbol

# List of supported assets in MT5 format
MT5_ASSETS = [oanda_to_mt5(symbol) for symbol in ASSETS]


# When run directly, display the configuration
if __name__ == "__main__":
    print("MT5 GENESIS EA Configuration:")
    print(f"ASSETS: {ASSETS}")
    print(f"MT5_ASSETS: {MT5_ASSETS}")
    print(f"TIMEFRAMES: {TIMEFRAMES}")
    print(f"DEFAULT_TIMEFRAME: {DEFAULT_TIMEFRAME}")
    print(f"SIGNAL_CONFIDENCE_THRESHOLD: {SIGNAL_CONFIDENCE_THRESHOLD}")
    
    # Check for API keys
    print("\nAPI Configuration:")
    print(f"OPENAI_API_KEY: {'Set' if OPENAI_API_KEY else 'Not set'}")
    print(f"OANDA_API_KEY: {'Set' if OANDA_API_KEY else 'Not set'}")
    print(f"OANDA_ACCOUNT_ID: {'Set' if OANDA_ACCOUNT_ID else 'Not set'}")
