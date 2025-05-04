#!/usr/bin/env python3
# Chart Generator Module Example
# This module demonstrates how to generate real trading charts using OANDA data

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
from datetime import datetime, timedelta
import os

from chart_generator_basic import ChartGenerator
from chart_utils import fetch_candles, generate_chart

def demo_bitcoin_chart():
    """
    Generate a Bitcoin example chart to demonstrate the charting capabilities
    with Japanese candlesticks, EMA 20, EMA 50, RSI, MACD, and ATR indicators.
    
    The chart will include:
    - Japanese candlesticks
    - EMA 20 (blue) and EMA 50 (orange) lines
    - RSI (14) in a separate panel
    - MACD (12,26,9) in a separate panel
    - ATR (14) in a separate panel
    - Entry point marked with a green arrow
    - Stop-loss level marked with a red line
    - Take-profit level marked with a green line
    """
    symbol = "BTC_USD"  # Using underscore format for internal system
    timeframe = "H1"  # 1-hour chart
    
    # Fetch the candle data from OANDA
    print(f"Fetching candle data for {symbol} ({timeframe})...")
    candles = fetch_candles(symbol, timeframe, count=100)
    
    if not candles:
        print("Failed to fetch candle data.")
        return
    
    # Setup entry, stop-loss, and take-profit parameters for annotation
    # Use the last candle's timestamp for the entry point
    last_timestamp = candles[-1]['timestamp']
    entry_price = candles[-1]['close']
    entry_point = (last_timestamp, entry_price)
    # Set more realistic TP/SL levels based on the instrument type
    if "USD" in symbol:
        # For forex and gold, use smaller percentages (0.5-1%)
        sl_price = entry_point[1] * 0.995  # 0.5% below entry for stop-loss
        tp_price = entry_point[1] * 1.01   # 1% above entry for take-profit
    else:
        # For other instruments, use slightly larger percentages (1-2%)
        sl_price = entry_point[1] * 0.99   # 1% below entry for stop-loss
        tp_price = entry_point[1] * 1.02   # 2% above entry for take-profit
    
    # Generate the chart with all indicators and annotations
    print("Generating chart with indicators and annotations...")
    chart_path = generate_chart(
        symbol=symbol,
        timeframe=timeframe,
        count=100,
        entry_point=entry_point,
        stop_loss=sl_price,
        take_profit=tp_price,
        signal_action="BUY_NOW"  # Specify this is an immediate buy signal
    )
    
    if chart_path:
        print(f"Chart generated successfully at: {chart_path}")
        # The ChartGenerator class already saves the chart in the correct folder structure
        # (static/charts/SYMBOL_NAME/SYMBOL_TIMEFRAME_TIMESTAMP.png) so no need to copy
    else:
        print("Failed to generate chart.")

def generate_anticipated_chart():
    """
    Generate an anticipated trade signal chart for Bitcoin
    showing potential entry, stop-loss, and take-profit levels
    """
    symbol = "BTC_USD"  # Using underscore format for internal system
    timeframe = "H1"  # 1-hour chart
    
    # Fetch the candle data from OANDA
    print(f"Fetching candle data for {symbol} ({timeframe})...")
    candles = fetch_candles(symbol, timeframe, count=100)
    
    if not candles:
        print("Failed to fetch candle data.")
        return
    
    # We'll use a point 10 candles back from the end for the anticipated entry
    entry_index = -10
    entry_timestamp = candles[entry_index]['timestamp']
    entry_price = candles[entry_index]['close']
    
    # Define anticipated levels
    stop_loss = entry_price * 0.98  # 2% below entry
    take_profit = entry_price * 1.03  # 3% above entry
    
    # Generate the anticipated trade chart with signal action type
    chart_path = generate_chart(
        symbol=symbol,
        timeframe=timeframe,
        count=100,
        entry_point=(entry_timestamp, entry_price),
        stop_loss=stop_loss,
        take_profit=take_profit,
        signal_action="ANTICIPATED_LONG"  # Specify signal action for proper marker positioning
    )
    
    if chart_path:
        print(f"Anticipated chart generated at: {chart_path}")
        # The ChartGenerator class already saves the chart in the correct folder structure
        # (static/charts/SYMBOL_NAME/SYMBOL_TIMEFRAME_TIMESTAMP.png) so no need to copy
    else:
        print("Failed to generate anticipated chart.")

def generate_closed_trade_chart():
    """
    Generate a chart showing a closed trade with result (win/loss)
    """
    symbol = "BTC_USD"  # Using underscore format for internal system
    timeframe = "H1"  # 1-hour chart
    
    # Fetch the candle data from OANDA
    print(f"Fetching candle data for {symbol} ({timeframe})...")
    candles = fetch_candles(symbol, timeframe, count=100)
    
    if not candles:
        print("Failed to fetch candle data.")
        return
    
    # Set up entry and exit points for a closed trade
    entry_index = -30  # Entry 30 candles back
    exit_index = -10   # Exit 10 candles back
    
    entry_timestamp = candles[entry_index]['timestamp']
    entry_price = candles[entry_index]['close']
    
    exit_price = candles[exit_index]['close']
    
    # Determine if the trade was a win or loss (for a BUY trade)
    result = "win" if exit_price > entry_price else "loss"
    
    # Set up stop-loss and take-profit based on entry price
    stop_loss = entry_price * 0.97  # 3% below entry
    take_profit = entry_price * 1.05  # 5% above entry
    
    # Generate the closed trade chart with result and signal action
    chart_path = generate_chart(
        symbol=symbol,
        timeframe=timeframe,
        count=100,
        entry_point=(entry_timestamp, entry_price),
        stop_loss=stop_loss,
        take_profit=take_profit,
        result=result,
        signal_action="BUY_NOW"  # Specify this was an immediate buy signal
    )
    
    if chart_path:
        print(f"Closed trade chart generated at: {chart_path}")
        
        # Save with standardized naming convention
        symbol_folder = f"static/charts/{symbol}"
        os.makedirs(symbol_folder, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        standardized_path = f"{symbol_folder}/{symbol}_{timeframe}_{timestamp}_{result.upper()}.png"
        
        # Copy the file to the standardized path
        import shutil
        shutil.copy(chart_path, standardized_path)
        print(f"Chart copied to standardized path: {standardized_path}")
    else:
        print("Failed to generate closed trade chart.")

if __name__ == "__main__":
    print("Chart Generator Examples")
    print("1. Generating Bitcoin current price chart...")
    demo_bitcoin_chart()
    
    print("\n2. Generating anticipated trade chart...")
    generate_anticipated_chart()
    
    print("\n3. Generating closed trade chart with result...")
    generate_closed_trade_chart()
    
    print("\nAll example charts generated successfully!")
