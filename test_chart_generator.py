import os
import sys
import json
import logging
import requests
from datetime import datetime, timedelta
from chart_generator_basic import ChartGenerator
from chart_utils import fetch_candles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of assets to test - focusing on just one major pair for testing
FOREX_ASSETS = ['EUR_USD']
TIMEFRAMES = ['M15']

def test_chart_generation():
    """Generate test charts for all key forex pairs"""
    
    # Set up output directory
    output_dir = 'test_charts'
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a test chart for each asset and timeframe
    for symbol in FOREX_ASSETS:
        for timeframe in TIMEFRAMES:
            logger.info(f"Generating test chart for {symbol} {timeframe}")
            
            try:
                # Fetch candle data (300 candles as configured in chart enhancement)
                candles = fetch_candles(symbol, timeframe, count=300)
                
                if not candles:
                    logger.error(f"Failed to fetch candles for {symbol} {timeframe}")
                    continue
                
                logger.info(f"Fetched {len(candles)} candles for {symbol} {timeframe}")
                
                # Create chart generator with both BUY_NOW and ANTICIPATED_LONG test cases
                for signal_type in ['BUY_NOW', 'ANTICIPATED_LONG']:
                    chart_gen = ChartGenerator(signal_action=signal_type)
                    
                    # Calculate entry point, SL, and TP for test
                    # For simplicity, use the last candle close price as entry
                    current_price = candles[-1]['close']
                    
                    if signal_type == 'BUY_NOW':
                        # For BUY_NOW, set entry at current price, SL below, TP above
                        entry_price = current_price
                        stop_loss = current_price * 0.99  # 1% below for test
                        take_profit = current_price * 1.02  # 2% above for test
                        
                        # Entry time will be now
                        entry_time = datetime.now()
                    else:  # ANTICIPATED_LONG
                        # For anticipated signals, set entry below current price
                        entry_price = current_price * 0.997  # 0.3% below current price
                        stop_loss = entry_price * 0.99  # 1% below entry
                        take_profit = entry_price * 1.02  # 2% above entry
                        
                        # Entry time is a bit in the future for anticipated signal
                        entry_time = datetime.now() + timedelta(hours=2)
                    
                    # Generate the chart
                    chart_path = chart_gen.create_chart(
                        candles=candles,
                        symbol=symbol,
                        timeframe=timeframe,
                        entry_point=(entry_time, entry_price),
                        stop_loss=stop_loss,
                        take_profit=take_profit
                    )
                    
                    if chart_path:
                        logger.info(f"Successfully generated chart: {chart_path}")
                    else:
                        logger.error(f"Failed to generate chart for {symbol} {timeframe} {signal_type}")
                        
            except Exception as e:
                logger.exception(f"Error generating chart for {symbol} {timeframe}: {str(e)}")

if __name__ == "__main__":
    test_chart_generation()
