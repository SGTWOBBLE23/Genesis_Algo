#!/usr/bin/env python3

"""
Test script to generate a chart with the previous style for comparison
"""

import os
import io
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union

# Import mplfinance for candlestick charts
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import mplfinance as mpf
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OldChartGenerator:
    """Class for generating technical analysis charts with the old styling"""
    
    def __init__(self, signal_action=None):
        # Configure matplotlib for non-interactive backend
        plt.switch_backend('agg')
        
        # Default chart size - high resolution for clear ChatGPT Vision analysis
        self.fig_width = 19.2
        self.fig_height = 10.8
        self.dpi = 100
        
        # Store signal action for positioning marker appropriately
        self.current_signal_action = signal_action
        
        # Output directory for saving charts
        self.output_dir = os.path.join('static', 'charts_old')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Colors for the chart elements with original thin candlesticks
        self.colors = {
            'bg': '#ffffff',
            'text': '#111111',
            'grid': '#D0D0D0',
            'candle_up': '#0E8B5C',
            'candle_down': '#D2384A',
            'ema20': '#0072EC',
            'ema50': '#EB7200',
            'volume': '#A0A0A0',
            'volume_up': '#0E8B5C',
            'volume_down': '#D2384A',
            'rsi': '#0072EC',
            'rsi_ob': '#D2384A',
            'rsi_os': '#0E8B5C',
            'macd': '#0072EC',
            'macd_signal': '#EB7200',
            'macd_hist_up': '#0E8B5C',
            'macd_hist_down': '#D2384A',
            'buy_entry': '#00BB00',
            'sell_entry': '#DD0000',
            'sl': '#DD0000',
            'tp': '#00BB00',
            'atr': '#9B30FF'
        }
    
    def _ema(self, series, length):
        """Calculate Exponential Moving Average"""
        return series.ewm(span=length, adjust=False).mean()
    
    def _rsi(self, series, length=14):
        """Calculate Relative Strength Index"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=length).mean()
        avg_loss = loss.rolling(window=length).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _macd(self, series, fast=12, slow=26, signal=9):
        """Calculate MACD indicator"""
        ema_fast = self._ema(series, fast)
        ema_slow = self._ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _atr(self, high, low, close, length=14):
        """Calculate Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.DataFrame({'tr1': tr1, 'tr2': tr2, 'tr3': tr3}).max(axis=1)
        atr = tr.rolling(window=length).mean()
        return atr
    
    def _prepare_data(self, candles: List[Dict]) -> pd.DataFrame:
        """Process candle data from OANDA API into pandas DataFrame"""
        data = []
        for candle in candles:
            if 'mid' in candle:
                price_data = candle['mid']
            elif 'ask' in candle:
                price_data = candle['ask']
            elif 'bid' in candle:
                price_data = candle['bid']
            else:
                logger.warning(f"Unknown candle format: {candle}")
                continue
            
            data.append({
                'time': candle['time'],
                'open': float(price_data['o']),
                'high': float(price_data['h']),
                'low': float(price_data['l']),
                'close': float(price_data['c']),
                'volume': float(candle['volume']) if 'volume' in candle else 0
            })
        
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        
        return df
    
    def create_chart(self, candles: List[Dict], symbol: str, timeframe: str,
                     entry_point: Optional[Tuple[datetime, float]] = None,
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None,
                     result: Optional[str] = None) -> str:
        """Create a chart with original thin candlesticks"""
        try:
            # Prepare the data
            df = self._prepare_data(candles)
            
            if df.empty:
                logger.error("No data to plot")
                return ""
            
            # Calculate indicators
            df['ema20'] = self._ema(df['close'], 20)
            df['ema50'] = self._ema(df['close'], 50)
            df['rsi'] = self._rsi(df['close'])
            df['macd'], df['macd_signal'], df['macd_hist'] = self._macd(df['close'])
            df['atr'] = self._atr(df['high'], df['low'], df['close'])
            
            # Log latest candle info for debugging
            if not df.empty:
                last_time = df.index[-1]
                last_close = df['close'].iloc[-1]
                logger.info(f"Latest candle data: time={last_time}, close price={last_close}")
            
            # Prepare the title
            display_symbol = symbol.replace('_', '/')
            current_date = datetime.now().strftime("%Y-%m-%d")
            title_suffix = f"{current_date}"
            
            if result:
                title = f"{display_symbol} ({timeframe}) - {result.upper()} - {title_suffix}"
            else:
                title = f"{display_symbol} ({timeframe}) - {title_suffix}"
                
            # Create a figure with subplots for price chart, volume, RSI, MACD, and ATR
            # Original height ratios
            fig, axes = plt.subplots(5, 1, figsize=(self.fig_width, self.fig_height), 
                                   gridspec_kw={'height_ratios': [6, 1, 2, 2, 1.5]})
            
            # Set background color
            fig.patch.set_facecolor(self.colors['bg'])
            for ax in axes:
                ax.set_facecolor(self.colors['bg'])
                ax.tick_params(colors=self.colors['text'])
                ax.spines['bottom'].set_color(self.colors['text'])
                ax.spines['top'].set_color(self.colors['text']) 
                ax.spines['left'].set_color(self.colors['text'])
                ax.spines['right'].set_color(self.colors['text'])
                ax.grid(color=self.colors['grid'], linestyle='--')
            
            # Set the title
            fig.suptitle(title, color=self.colors['text'], fontsize=14)
            
            # Plot candlesticks on the main chart
            up = df['close'] > df['open']
            down = df['close'] <= df['open']
            
            # Plot candlestick wicks with original thin wicks
            axes[0].vlines(df.index[up], df['low'][up], df['high'][up], color=self.colors['candle_up'])
            axes[0].vlines(df.index[down], df['low'][down], df['high'][down], color=self.colors['candle_down'])
            
            # Plot candlestick bodies with original thin width
            width = 0.6  # original width
            for i, (idx, row) in enumerate(df.iterrows()):
                if row['close'] > row['open']:
                    # Bullish candle
                    rect = plt.Rectangle((i - width/2, row['open']), width, row['close'] - row['open'],
                                      fill=True, color=self.colors['candle_up'])
                    axes[0].add_patch(rect)
                else:
                    # Bearish candle
                    rect = plt.Rectangle((i - width/2, row['close']), width, row['open'] - row['close'],
                                      fill=True, color=self.colors['candle_down'])
                    axes[0].add_patch(rect)
            
            # Plot EMAs on main chart with original thin lines
            axes[0].plot(np.arange(len(df)), df['ema20'], color=self.colors['ema20'], linewidth=1.5, label='EMA 20')
            axes[0].plot(np.arange(len(df)), df['ema50'], color=self.colors['ema50'], linewidth=1.5, label='EMA 50')
            
            # Add legend
            axes[0].legend(loc='upper left')
            
            # Set labels
            axes[0].set_ylabel('Price', color=self.colors['text'])
            
            # Plot volume on the second panel
            for i in range(len(df)):
                if i >= len(df) or not 'volume' in df.columns or pd.isna(df['volume'].iloc[i]):
                    continue
                vol_val = df['volume'].iloc[i]
                if i > 0 and df['close'].iloc[i] > df['open'].iloc[i]:
                    axes[1].bar(i, vol_val, width=0.8, color=self.colors['volume_up'])
                else:
                    axes[1].bar(i, vol_val, width=0.8, color=self.colors['volume_down'])
            
            axes[1].set_ylabel('Volume', color=self.colors['text'])
            
            # Plot RSI on the third panel
            axes[2].plot(np.arange(len(df)), df['rsi'], color=self.colors['rsi'])
            axes[2].axhline(y=30, color=self.colors['rsi_os'], linestyle='--')
            axes[2].axhline(y=70, color=self.colors['rsi_ob'], linestyle='--')
            axes[2].set_ylim(0, 100)
            axes[2].set_ylabel('RSI (14)', color=self.colors['text'])
            
            # Plot MACD on the fourth panel
            axes[3].plot(np.arange(len(df)), df['macd'], color=self.colors['macd'], label='MACD')
            axes[3].plot(np.arange(len(df)), df['macd_signal'], color=self.colors['macd_signal'], label='Signal')
            axes[3].axhline(y=0, color=self.colors['grid'], linestyle='-')
            axes[3].legend(loc='upper left')
            
            # Add MACD histogram
            for i in range(len(df)):
                if i >= len(df['macd_hist']):
                    continue
                hist_val = df['macd_hist'].iloc[i]
                if hist_val >= 0:
                    axes[3].bar(i, hist_val, width=0.8, color=self.colors['macd_hist_up'], alpha=0.5)
                else:
                    axes[3].bar(i, hist_val, width=0.8, color=self.colors['macd_hist_down'], alpha=0.5)
            
            axes[3].set_ylabel('MACD (12,26,9)', color=self.colors['text'])
            
            # Plot ATR on the fifth panel
            axes[4].plot(np.arange(len(df)), df['atr'], color=self.colors['atr'])
            axes[4].set_ylabel('ATR (14)', color=self.colors['text'])
            
            # Set x-axis labels
            x_positions = np.linspace(0, len(df) - 1, min(10, len(df)))
            x_labels = [df.index[int(pos)].strftime('%Y-%m-%d %H:%M') for pos in x_positions]
            
            for ax in axes:
                ax.set_xticks(x_positions)
                ax.set_xticklabels(x_labels, rotation=45)
            
            # Set x-axis ranges
            for ax in axes:
                ax.set_xlim(0, len(df))
            
            # Add spacing between subplots
            plt.tight_layout()
            
            # Save the chart
            clean_symbol = symbol.replace('_', '')
            symbol_dir = os.path.join(self.output_dir, clean_symbol)
            os.makedirs(symbol_dir, exist_ok=True)
            
            current_datetime = datetime.now()
            now = current_datetime.strftime("%Y%m%d_%H%M%S")
            result_str = f"_{result.lower()}" if result else ""
            filename = f"{clean_symbol}_{timeframe}_{now}{result_str}_old.png"
            filepath = os.path.join(symbol_dir, filename)
            
            plt.savefig(filepath, dpi=self.dpi, bbox_inches='tight')
            logger.info(f"Chart saved to {filepath}")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Error creating chart: {str(e)}")
            return ""

# Function to load OANDA candles
def load_candles(symbol, count=50):
    import json
    import requests
    import os
    
    try:
        # OANDA API configuration
        api_key = os.environ.get('OANDA_API_KEY', 'YourOandaApiKey') 
        account_id = os.environ.get('OANDA_ACCOUNT_ID', 'YourOandaAccountId')
        oanda_url = 'https://api-fxpractice.oanda.com'
        
        # Prepare the request
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # Construct the URL
        url = f"{oanda_url}/v3/instruments/{symbol}/candles?granularity=H1&count={count}"
        
        # Make the request
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get('candles', [])
        else:
            logger.error(f"Failed to get OANDA data: {response.text}")
            # Return some sample data for testing
            return [
                {"time": "2023-01-01T00:00:00Z", "mid": {"o": "1.0700", "h": "1.0750", "l": "1.0690", "c": "1.0720"}, "volume": 100},
                {"time": "2023-01-01T01:00:00Z", "mid": {"o": "1.0720", "h": "1.0730", "l": "1.0700", "c": "1.0710"}, "volume": 120},
                # Add more sample points
            ]
    except Exception as e:
        logger.error(f"Error loading candles: {str(e)}")
        return []

# Main function to generate comparison chart
def generate_comparison_chart():
    symbol = "EUR_USD"
    logger.info(f"Generating comparison chart for {symbol}")
    
    try:
        # Load candle data
        candles = load_candles(symbol, count=50)  # Fewer candles for clearer view of differences
        
        if not candles:
            logger.error("No candle data available")
            return
        
        # Create chart with original styling
        chart_generator = OldChartGenerator()
        old_chart_path = chart_generator.create_chart(
            candles=candles,
            symbol=symbol,
            timeframe="H1",
            result=None  # No result label
        )
        
        if old_chart_path:
            logger.info(f"Generated old style chart at {old_chart_path}")
            return old_chart_path
        else:
            logger.error("Failed to generate old style chart")
    
    except Exception as e:
        logger.error(f"Error in generate_comparison_chart: {str(e)}")

if __name__ == "__main__":
    chart_path = generate_comparison_chart()
    print(f"Comparison chart created at: {chart_path}")
