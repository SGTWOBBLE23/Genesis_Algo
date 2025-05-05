#!/usr/bin/env python3

"""
Test script to generate charts for the remaining assets with the light theme styling
"""

import logging
from datetime import datetime, timedelta

from chart_utils import generate_chart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_remaining_charts():
    """Generate test charts for XAU_USD and GBP_JPY with the enhanced styling"""
    
    # Test the two remaining assets
    remaining_assets = ["XAU_USD", "GBP_JPY"]
    
    for symbol in remaining_assets:
        try:
            logger.info(f"Generating enhanced chart for {symbol}")
            
            # Create chart with sample entry, SL, and TP levels
            entry_time = datetime.now() - timedelta(hours=1)
            
            # Generate chart
            chart_path = generate_chart(
                symbol=symbol,
                timeframe="H1",
                count=100,  # fewer candles for faster generation
                entry_point=(entry_time, 1.0),  # dummy price, will be adjusted in the function
                stop_loss=0.9,  # dummy price, will be adjusted
                take_profit=1.1,  # dummy price, will be adjusted
                signal_action="BUY_NOW"
            )
            
            if chart_path:
                logger.info(f"Successfully created chart at {chart_path}")
            else:
                logger.error(f"Failed to create chart for {symbol}")
                
        except Exception as e:
            logger.error(f"Error generating chart for {symbol}: {e}")

if __name__ == "__main__":
    test_remaining_charts()
    print("\nChart generation test completed. Check the static/charts directory for results.")
