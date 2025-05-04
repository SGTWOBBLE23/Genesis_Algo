import os
import logging
from datetime import datetime, timedelta
from chart_utils import generate_chart

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_generate_chart():
    # Test with a standard forex pair
    symbol = "EUR_USD"
    timeframe = "H1"
    count = 100
    
    # Set a simulated entry point (24 hours ago)
    entry_time = datetime.now() - timedelta(days=1)
    entry_price = 1.08000  # Sample price
    
    # Set stop loss and take profit
    stop_loss = entry_price - 0.00200
    take_profit = entry_price + 0.00400
    
    # Generate chart with simulated trade data
    chart_path = generate_chart(
        symbol=symbol,
        timeframe=timeframe,
        count=count,
        entry_point=(entry_time, entry_price),
        stop_loss=stop_loss,
        take_profit=take_profit,
        result="win"
    )
    
    logger.info(f"Generated chart at: {chart_path}")
    
    # Test with gold
    symbol = "XAU_USD"
    timeframe = "H4"
    count = 50
    
    # Set a simulated entry point (3 days ago)
    entry_time = datetime.now() - timedelta(days=3)
    entry_price = 2300.00  # Sample price
    
    # Set stop loss and take profit
    stop_loss = entry_price - 20.00
    take_profit = entry_price + 40.00
    
    # Generate chart with simulated trade data
    chart_path = generate_chart(
        symbol=symbol,
        timeframe=timeframe,
        count=count,
        entry_point=(entry_time, entry_price),
        stop_loss=stop_loss,
        take_profit=take_profit,
        result="loss"
    )
    
    logger.info(f"Generated chart at: {chart_path}")
    
    return True

if __name__ == "__main__":
    try:
        successful = test_generate_chart()
        logger.info(f"Test {'successful' if successful else 'failed'}")
    except Exception as e:
        logger.error(f"Test failed with error: {str(e)}")
