import os
import logging
from datetime import datetime
from chart_generator_basic import ChartGenerator
from chart_utils import fetch_candles

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test parameters
symbol = "GBP_JPY"
timeframe = "M15"

def test_chart():
    """Generate a test chart for GBP_USD M15"""
    try:
        # Fetch candle data
        logger.info(f"Fetching candles for {symbol} {timeframe}")
        candles = fetch_candles(symbol, timeframe, count=100)
        
        if not candles or len(candles) == 0:
            logger.error(f"No candles found for {symbol} {timeframe}")
            return
            
        logger.info(f"Fetched {len(candles)} candles for {symbol} {timeframe}")
        
        # Create chart generator
        logger.info("Creating chart generator with BUY_NOW signal")
        chart_gen = ChartGenerator(signal_action="BUY_NOW")
        
        # Calculate entry point, SL, and TP
        current_price = candles[-1]['close']
        logger.info(f"Latest close price: {current_price}")
        
        entry_price = current_price
        stop_loss = current_price * 0.99  # 1% below
        take_profit = current_price * 1.02  # 2% above
        entry_time = datetime.now()
        
        # Generate the chart
        logger.info("Generating chart...")
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
            return chart_path
        else:
            logger.error("Failed to generate chart")
            
    except Exception as e:
        logger.exception(f"Error in test_chart: {str(e)}")

if __name__ == "__main__":
    test_chart()
