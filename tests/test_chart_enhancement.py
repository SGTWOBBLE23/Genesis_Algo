#!/usr/bin/env python3

"""
Test script for the enhanced chart generator
This script generates a test chart with all the requested GENESIS Vision enhancements:
- Volume pane with color-coded bars
- ATR as a thin line in a separate panel
- Increased historical lookback (300 candles)
- Improved legibility with 1080p resolution (19.2 x 10.8)
- Dark theme preservation for better AI analysis
"""

import os
import sys
from datetime import datetime

from chart_generator_basic import ChartGenerator
from oanda_api import OandaAPI


def generate_enhanced_test_chart():
    """Generate test chart with all requested enhancements"""
    print("Generating enhanced GENESIS test chart...")
    
    # Create OANDA API instance with environment credentials
    oanda = OandaAPI(api_key=os.environ.get("OANDA_API_KEY"),
                     account_id=os.environ.get("OANDA_ACCOUNT_ID"))
    
    # Fetch candles with increased historical lookback (300)
    symbol = "EUR_USD"  # One of the focus forex pairs
    timeframe = "H1"
    candles = oanda.get_candles(symbol, timeframe, 300)
    
    if not candles:
        print(f"Error: Could not fetch candles for {symbol}")
        return None
    
    print(f"Successfully fetched {len(candles)} candles for {symbol}")
    
    # Calculate sample entry point, SL and TP
    entry_time = datetime.now()
    entry_price = candles[-1]['close']  # Use current price as entry
    
    # Sample stop-loss and take-profit levels
    sl = entry_price - (0.005 * entry_price)  # 0.5% below entry
    tp = entry_price + (0.01 * entry_price)   # 1% above entry
    
    # Generate chart with 'BUY_NOW' signal action
    print(f"Generating enhanced chart for {symbol}...")
    chart_gen = ChartGenerator(signal_action="BUY_NOW")
    
    chart_path = chart_gen.create_chart(
        candles=candles,
        symbol=symbol,
        timeframe=timeframe,
        entry_point=(entry_time, entry_price),
        stop_loss=sl,
        take_profit=tp
    )
    
    if chart_path:
        print(f"GENESIS Enhanced chart saved to: {chart_path}")
        return chart_path
    else:
        print("Error: Failed to generate chart")
        return None


if __name__ == "__main__":
    chart_path = generate_enhanced_test_chart()
    if chart_path:
        print("Test successful!")
        # If you want to open the chart, use PIL
        try:
            from PIL import Image
            Image.open(chart_path).show()
            print("Opened chart for viewing")
        except ImportError:
            print("PIL not available, chart not opened for viewing")
    else:
        print("Test failed!")
        sys.exit(1)
