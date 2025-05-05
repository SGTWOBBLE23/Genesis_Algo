#!/usr/bin/env python3

"""
Test script to generate a chart with the new light theme styling
and numeric price overlays to verify the improvements.
"""

import os
import logging
from datetime import datetime, timedelta

from chart_utils import generate_chart
from config import ASSETS

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_enhanced_chart():
    """Generate test charts for each symbol with the enhanced styling"""
    os.makedirs("test_charts", exist_ok=True)
    
    # Test for each of the 5 restricted assets
    for symbol in ASSETS[:2]:  # Just test the first 2 for speed
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
    test_enhanced_chart()
    print("\nChart generation test completed. Check the static/charts directory for results.")
