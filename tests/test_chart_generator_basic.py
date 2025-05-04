import os
import logging
import json
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from chart_generator_basic import ChartGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_sample_candles(days=50):
    """Generate sample candle data in OANDA API format"""
    candles = []
    start_date = datetime.now() - timedelta(days=days)
    
    # Starting price
    price = 1.1000  # EUR/USD like price
    
    for i in range(days * 24):  # Hourly candles
        # Random price movement with slight upward bias
        change = random.normalvariate(0.0001, 0.0005)  # Mean, std dev
        price += change
        
        # Create hourly candle
        candle_time = start_date + timedelta(hours=i)
        open_price = price
        close_price = price + random.normalvariate(0, 0.0003)
        high_price = max(open_price, close_price) + abs(random.normalvariate(0, 0.0002))
        low_price = min(open_price, close_price) - abs(random.normalvariate(0, 0.0002))
        volume = random.randint(500, 1500)
        
        candle = {
            'timestamp': candle_time.isoformat(),
            'open': open_price,
            'high': high_price,
            'low': low_price,
            'close': close_price,
            'volume': volume
        }
        
        candles.append(candle)
    
    return candles

def test_chart_generator():
    """Test the ChartGenerator with sample data"""
    # Create sample data
    candles = generate_sample_candles(days=30)
    
    # Create chart generator instance
    chart_gen = ChartGenerator()
    
    # Test with basic setup
    result = chart_gen.create_chart(
        candles=candles,
        symbol="EUR_USD",
        timeframe="H1"
    )
    print(f"Basic chart created: {result}")
    
    # Test with entry, stop loss and take profit
    entry_time = datetime.now() - timedelta(days=10)
    entry_price = candles[len(candles) // 2]['close']
    stop_loss = entry_price - 0.0050
    take_profit = entry_price + 0.0080
    
    result = chart_gen.create_chart(
        candles=candles,
        symbol="EUR_USD",
        timeframe="H1",
        entry_point=(entry_time, entry_price),
        stop_loss=stop_loss,
        take_profit=take_profit,
        result="win"
    )
    print(f"Chart with annotations created: {result}")
    
    # Test chart_bytes function
    chart_bytes = chart_gen.create_chart_bytes(
        candles=candles,
        symbol="EUR_USD",
        timeframe="H1"
    )
    print(f"Chart bytes created: {len(chart_bytes)} bytes")
    
    return True

if __name__ == "__main__":
    try:
        test_chart_generator()
        print("Chart generator tests passed successfully!")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise