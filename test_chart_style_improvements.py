#!/usr/bin/env python3

"""
Test script to verify the improved chart styling with larger Japanese candlesticks
"""

import logging
from datetime import datetime, timedelta

from chart_utils import generate_chart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_improved_charts():
    """Generate enhanced test charts for all restricted assets"""
    # List of all restricted assets to test
    assets = ["EUR_USD", "GBP_USD", "USD_JPY", "XAU_USD", "GBP_JPY"]
    
    # Test each asset
    for symbol in assets:
        try:
            logger.info(f"Generating improved chart for {symbol}")
            
            # Create chart with sample entry, SL, and TP levels
            entry_time = datetime.now() - timedelta(hours=1)
            
            # Generate chart for sell action to test different marker
            chart_path = generate_chart(
                symbol=symbol,
                timeframe="H1",
                count=100,  # Standard number of candles
                entry_point=(entry_time, 1.0),  # Dummy price, will adjust automatically
                stop_loss=0.9,  # Dummy price, will adjust
                take_profit=1.1,  # Dummy price, will adjust
                signal_action="SELL_NOW"  # Test SELL signals for red markers
            )
            
            if chart_path:
                logger.info(f"Successfully created chart with SELL signal at {chart_path}")
            else:
                logger.error(f"Failed to create chart for {symbol}")
            
        except Exception as e:
            logger.error(f"Error generating chart for {symbol}: {e}")

if __name__ == "__main__":
    test_improved_charts()
    print("\nImproved chart style test completed. Check the static/charts directory for results.")
