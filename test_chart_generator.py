import os
import sys
import json
import logging
import argparse
import requests
from datetime import datetime, timedelta
from chart_generator_basic import ChartGenerator
from chart_utils import fetch_candles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of all key forex assets to test
FOREX_ASSETS = ['EUR_USD', 'GBP_USD', 'USD_JPY', 'USD_CAD', 'GBP_JPY', 'XAU_USD']
TIMEFRAMES = ['M15', 'H1']

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

def test_specific_asset(symbol, timeframe=None):
    """Generate test chart for a specific asset and timeframe"""
    timeframes_to_test = [timeframe] if timeframe else TIMEFRAMES
    
    # Set up output directory
    output_dir = 'test_charts'
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"Testing specific asset: {symbol}")
    
    for tf in timeframes_to_test:
        logger.info(f"Generating test chart for {symbol} {tf}")
        
        try:
            # Fetch candle data
            candles = fetch_candles(symbol, tf, count=300)
            
            if not candles:
                logger.error(f"Failed to fetch candles for {symbol} {tf}")
                continue
            
            logger.info(f"Fetched {len(candles)} candles for {symbol} {tf}")
            
            # Create chart with BUY_NOW signal type
            chart_gen = ChartGenerator(signal_action="BUY_NOW")
            
            # Calculate entry point, SL, and TP for test
            current_price = candles[-1]['close']
            entry_price = current_price
            stop_loss = current_price * 0.99  # 1% below for test
            take_profit = current_price * 1.02  # 2% above for test
            entry_time = datetime.now()
            
            # Generate the chart
            chart_path = chart_gen.create_chart(
                candles=candles,
                symbol=symbol,
                timeframe=tf,
                entry_point=(entry_time, entry_price),
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            if chart_path:
                logger.info(f"Successfully generated chart: {chart_path}")
                # Return a successful result for checking
                return chart_path
            else:
                logger.error(f"Failed to generate chart for {symbol} {tf}")
                
        except Exception as e:
            logger.exception(f"Error generating chart for {symbol} {tf}: {str(e)}")
    
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate test charts for forex assets')
    parser.add_argument('--symbol', type=str, help='Specific symbol to test (e.g., EUR_USD)')
    parser.add_argument('--timeframe', type=str, help='Specific timeframe to test (e.g., M15, H1)')
    args = parser.parse_args()
    
    if args.symbol:
        # Test a specific asset
        test_specific_asset(args.symbol, args.timeframe)
    else:
        # Test all assets
        test_chart_generation()
