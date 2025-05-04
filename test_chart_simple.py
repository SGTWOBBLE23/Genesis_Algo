import os
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a simple test function
def create_test_chart():
    # Create a directory for the charts
    os.makedirs('static/charts', exist_ok=True)
    
    # Generate sample OHLCV data
    dates = pd.date_range(start=datetime.now()-timedelta(days=50), periods=50, freq='D')
    
    # Create sample price data with an uptrend
    np.random.seed(42)  # For reproducibility
    closes = np.random.normal(loc=100, scale=2, size=50).cumsum()
    opens = closes - np.random.normal(loc=0, scale=1, size=50)
    highs = np.maximum(opens, closes) + np.random.normal(loc=1, scale=0.5, size=50)
    lows = np.minimum(opens, closes) - np.random.normal(loc=1, scale=0.5, size=50)
    volumes = np.random.normal(loc=1000, scale=200, size=50)
    
    # Create the DataFrame in the format required by mplfinance
    df = pd.DataFrame({
        'Open': opens,
        'High': highs,
        'Low': lows,
        'Close': closes,
        'Volume': volumes
    }, index=dates)
    
    # Create simple EMAs for the price chart
    df['ema20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # Simple RSI calculation
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Define style
    style = mpf.make_mpf_style(
        base_mpf_style='charles',
        figcolor='#121826',
        facecolor='#121826',
        edgecolor='#e0e0e0',
        marketcolors={
            'candle': {'up': '#26a69a', 'down': '#ef5350'},
            'edge': {'up': '#26a69a', 'down': '#ef5350'},
            'wick': {'up': '#26a69a', 'down': '#ef5350'},
            'ohlc': {'up': '#26a69a', 'down': '#ef5350'},
            'volume': {'up': '#26a69a', 'down': '#ef5350'}
        }
    )
    
    # Create the add_plots for additional data
    add_plots = [
        mpf.make_addplot(df['ema20'], color='#2962ff'),
        mpf.make_addplot(df['ema50'], color='#ff9800'),
        mpf.make_addplot(df['rsi'], panel=1, color='#2962ff', ylabel='RSI')
    ]
    
    # Create and save the chart
    filename = f'static/charts/test_chart_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    
    # Create figure with mplfinance
    fig, axes = mpf.plot(
        df,
        type='candle',
        style=style,
        title="Test Chart - EUR/USD",
        figsize=(12.8, 7.2),
        panel_ratios=(6, 2),
        addplot=add_plots,
        volume=True,
        returnfig=True
    )
    
    # Get the axes to add horizontal lines
    ax_main = axes[0]
    ax_rsi = axes[2]
    
    # Add horizontal RSI lines - no alpha parameter
    ax_rsi.axhline(y=30, color='#26a69a', linestyle='-.')
    ax_rsi.axhline(y=70, color='#ef5350', linestyle='-.')
    
    # Add stop loss and take profit lines - no alpha parameter
    stop_loss = df['Close'].iloc[-1] * 0.95
    take_profit = df['Close'].iloc[-1] * 1.05
    
    ax_main.axhline(y=stop_loss, color='#ff0000', linestyle='-.', linewidth=1.5, label='Stop Loss')
    ax_main.axhline(y=take_profit, color='#00ff00', linestyle='-.', linewidth=1.5, label='Take Profit')
    
    # Add legend
    ax_main.legend(loc='upper left')
    
    # Save the figure
    fig.savefig(filename, dpi=100, bbox_inches='tight')
    plt.close(fig)
    
    logger.info(f"Test chart created: {filename}")
    return filename

if __name__ == "__main__":
    try:
        chart_path = create_test_chart()
        print(f"Chart generated successfully at: {chart_path}")
    except Exception as e:
        logger.error(f"Error generating chart: {str(e)}")
