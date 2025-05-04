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

class ChartGenerator:
    """Class for generating technical analysis charts with indicators using mplfinance"""
    
    def __init__(self):
        # Configure matplotlib for non-interactive backend
        plt.switch_backend('agg')
        
        # Default chart size - high resolution for clear ChatGPT Vision analysis
        self.fig_width = 12.8
        self.fig_height = 7.2
        self.dpi = 100  # 1280x720 resolution
        
        # Dark theme colors for mplfinance
        self.colors = {
            'bg': '#121826',            # Background color
            'text': '#e0e0e0',          # Text color
            'grid': '#2a2e39',          # Grid color
            'candle_up': '#26a69a',     # Bullish candle color
            'candle_down': '#ef5350',   # Bearish candle color
            'ema20': '#2962ff',         # Blue
            'ema50': '#ff9800',         # Orange
            'volume': '#2a2e39',        # Volume bars base color
            'volume_up': '#26a69a',     # Up volume bar color
            'volume_down': '#ef5350',   # Down volume bar color
            'rsi': '#2962ff',           # RSI line color
            'rsi_ob': '#ef5350',        # Overbought line color
            'rsi_os': '#26a69a',        # Oversold line color
            'macd': '#2962ff',          # MACD line color
            'macd_signal': '#ff9800',   # Signal line color
            'macd_hist_up': '#26a69a',  # MACD histogram up color
            'macd_hist_down': '#ef5350',# MACD histogram down color
            'entry': '#00ff00',         # Green arrow for entry point
            'sl': '#ff0000',            # Red line (stop loss)
            'tp': '#00ff00'             # Green line (take profit)
        }
        
        # Default style setup for mplfinance
        self.style = mpf.make_mpf_style(
            base_mpf_style='charles',
            figcolor=self.colors['bg'],
            facecolor=self.colors['bg'],
            edgecolor=self.colors['text'],
            gridcolor=self.colors['grid'],
            gridstyle='--',
            gridaxis='both',
            y_on_right=False,
            marketcolors={
                'candle': {'up': self.colors['candle_up'], 'down': self.colors['candle_down']},
                'edge': {'up': self.colors['candle_up'], 'down': self.colors['candle_down']},
                'wick': {'up': self.colors['candle_up'], 'down': self.colors['candle_down']},
                'ohlc': {'up': self.colors['candle_up'], 'down': self.colors['candle_down']},
                'volume': {'up': self.colors['volume_up'], 'down': self.colors['volume_down']},
            },
            rc={'axes.labelcolor': self.colors['text'],
                'axes.edgecolor': self.colors['text'],
                'xtick.color': self.colors['text'],
                'ytick.color': self.colors['text'],
                'figure.titlesize': 'x-large',
                'figure.titleweight': 'bold'}
        )
        
        # Directory to save charts
        self.output_dir = os.path.join(os.getcwd(), 'static', 'charts')
        os.makedirs(self.output_dir, exist_ok=True)
    
    # Helper methods for calculating indicators
    def _ema(self, series, length):
        """Calculate Exponential Moving Average"""
        return series.ewm(span=length, adjust=False).mean()
    
    def _rsi(self, series, length=14):
        """Calculate Relative Strength Index"""
        # Calculate price changes
        delta = series.diff()
        
        # Separate gains and losses
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        # Calculate average gain and loss
        avg_gain = gain.rolling(window=length).mean()
        avg_loss = loss.rolling(window=length).mean()
        
        # Calculate RS and RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _macd(self, series, fast=12, slow=26, signal=9):
        """Calculate MACD indicator"""
        # Calculate EMAs
        ema_fast = self._ema(series, fast)
        ema_slow = self._ema(series, slow)
        
        # Calculate MACD line
        macd_line = ema_fast - ema_slow
        
        # Calculate signal line
        signal_line = self._ema(macd_line, signal)
        
        # Calculate histogram
        histogram = macd_line - signal_line
        
        return pd.DataFrame({
            'macd': macd_line,
            'macd_signal': signal_line,
            'macd_hist': histogram
        })
    
    def _atr(self, high, low, close, length=14):
        """Calculate Average True Range"""
        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        # Combine to get True Range
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR
        atr = tr.rolling(window=length).mean()
        
        return atr
    
    def _prepare_data(self, candles: List[Dict]) -> pd.DataFrame:
        """Process candle data from OANDA API into pandas DataFrame
        
        Args:
            candles: List of candle dictionaries from OANDA API
            
        Returns:
            DataFrame in mplfinance format (OHLCV)
        """
        # Create DataFrame from candles list
        df = pd.DataFrame(candles)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Rename columns to mplfinance standard format
        df = df.rename(columns={
            'timestamp': 'datetime',
            'open': 'Open',   # MPLFinance uses capitalized column names
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        # Set datetime as index (required by mplfinance)
        df = df.set_index('datetime')
        
        # Add indicators
        # EMA 20 and 50
        df['ema20'] = self._ema(df['Close'], 20)
        df['ema50'] = self._ema(df['Close'], 50)
        
        # RSI-14
        df['rsi'] = self._rsi(df['Close'], 14)
        
        # MACD (12, 26, 9)
        macd_data = self._macd(df['Close'], 12, 26, 9)
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['macd_signal']
        df['macd_hist'] = macd_data['macd_hist']
        
        # ATR-14
        df['atr'] = self._atr(df['High'], df['Low'], df['Close'], 14)
        
        return df
        
    def create_chart(self, candles: List[Dict], symbol: str, timeframe: str,
                     entry_point: Optional[Tuple[datetime, float]] = None,
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None,
                     result: Optional[str] = None) -> str:
        """Create a complete technical analysis chart with annotations using mplfinance
        
        Args:
            candles: List of candle dictionaries from OANDA API
            symbol: Trading symbol/instrument name (e.g., "EUR_USD")
            timeframe: Chart timeframe (e.g., "H1")
            entry_point: Optional tuple of (datetime, price) for entry annotation
            stop_loss: Optional price level for stop loss line
            take_profit: Optional price level for take profit line
            result: Optional trade result ("win" or "loss")
            
        Returns:
            Path to saved chart image
        """
        # Format the symbol for display (EUR_USD -> EUR/USD)
        display_symbol = symbol.replace("_", "/")
        
        # Prepare the data for plotting
        df = self._prepare_data(candles)
        
        # Calculate latest ATR value for title
        latest_atr = df['atr'].iloc[-1] if not df['atr'].empty else 0
        
        # Setup the title with symbol, timeframe, result (if any) and ATR
        title_suffix = f"ATR(14): {latest_atr:.5f}"
        if result:
            title = f"{display_symbol} ({timeframe}) - {result.upper()} - {title_suffix}"
        else:
            title = f"{display_symbol} ({timeframe}) - {title_suffix}"
            
        # Define EMAs for the price chart
        apds = [
            # EMA 20 and 50 on price chart
            mpf.make_addplot(df['ema20'], color=self.colors['ema20'], width=1.5),
            mpf.make_addplot(df['ema50'], color=self.colors['ema50'], width=1.5),
            
            # RSI in panel 1
            mpf.make_addplot(df['rsi'], panel=1, color=self.colors['rsi'], width=1.5,
                            ylabel='RSI (14)', secondary_y=False),
                            
            # MACD and signal in panel 2
            mpf.make_addplot(df['macd'], panel=2, color=self.colors['macd'], width=1.5,
                           secondary_y=False),
            mpf.make_addplot(df['macd_signal'], panel=2, color=self.colors['macd_signal'], width=1.5,
                           secondary_y=False)
        ]
        
        # Add the MACD histogram with correct coloring (green for positive, red for negative)
        macd_hist_colors = [self.colors['macd_hist_up'] if val > 0 else self.colors['macd_hist_down']
                          for val in df['macd_hist']]
        apds.append(mpf.make_addplot(df['macd_hist'], type='bar', panel=2, color=macd_hist_colors, alpha=0.5,
                                  secondary_y=False))
        
        # Additional customizations through kwarg dict
        plot_kwargs = {
            'type': 'candle',
            'style': self.style,
            'title': title,
            'figsize': (self.fig_width, self.fig_height),
            'panel_ratios': (6, 2, 2),  # Main chart, RSI, MACD
            'addplot': apds,
            'volume': True,
            'ylabel': f'Price ({display_symbol})',
            'datetime_format': '%m-%d %H:%M',
            'tight_layout': True,
            'scale_padding': {'left': 0.1, 'right': 1.1, 'top': 0.8, 'bottom': 0.8}
        }
        
        # Generate filename with timestamp
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_str = f"_{result.upper()}" if result else ""
        filename = f"{symbol}_{timeframe}_{now}{result_str}.png"
        filepath = os.path.join(self.output_dir, filename)
        
        # Create folder if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create the figure first manually
        fig, axes = mpf.plot(df, **plot_kwargs, returnfig=True)
        
        # Get the axes objects
        ax_main = axes[0]  # Main price chart
        ax_rsi = axes[2]   # RSI panel 
        ax_macd = axes[3]  # MACD panel
        
        # Manually add horizontal lines on RSI panel
        ax_rsi.axhline(y=30, color=self.colors['rsi_os'], linestyle='--', alpha=0.5)
        ax_rsi.axhline(y=70, color=self.colors['rsi_ob'], linestyle='--', alpha=0.5)
        
        # Add horizontal line at zero for MACD panel
        ax_macd.axhline(y=0, color=self.colors['grid'], linestyle='-', alpha=0.3)
        
        # Add stop loss and take profit lines on main price chart if provided
        if stop_loss is not None:
            ax_main.axhline(y=stop_loss, color=self.colors['sl'], linestyle='--', 
                         alpha=0.7, linewidth=1.5, label='Stop Loss')
        
        if take_profit is not None:
            ax_main.axhline(y=take_profit, color=self.colors['tp'], linestyle='--', 
                         alpha=0.7, linewidth=1.5, label='Take Profit')
        
        # Add legend for price chart
        handles, labels = ax_main.get_legend_handles_labels()
        if handles:
            ax_main.legend(loc='upper left', framealpha=0.5)
        
        # Save the figure to file
        fig.savefig(filepath, dpi=self.dpi, bbox_inches='tight')
        plt.close(fig)  # Close the figure to free memory
        
        logger.info(f"Chart saved to {filepath}")
        return filepath
    
    def create_chart_bytes(self, candles: List[Dict], symbol: str, timeframe: str,
                         entry_point: Optional[Tuple[datetime, float]] = None,
                         stop_loss: Optional[float] = None,
                         take_profit: Optional[float] = None,
                         result: Optional[str] = None) -> bytes:
        """Create chart and return as bytes for in-memory processing
        
        This is useful for directly sending charts via API without saving to disk
        """
        # Format the symbol for display (EUR_USD -> EUR/USD)
        display_symbol = symbol.replace("_", "/")
        
        # Prepare the data for plotting
        df = self._prepare_data(candles)
        
        # Calculate latest ATR value for title
        latest_atr = df['atr'].iloc[-1] if not df['atr'].empty else 0
        
        # Setup the title with symbol, timeframe, result (if any) and ATR
        title_suffix = f"ATR(14): {latest_atr:.5f}"
        if result:
            title = f"{display_symbol} ({timeframe}) - {result.upper()} - {title_suffix}"
        else:
            title = f"{display_symbol} ({timeframe}) - {title_suffix}"
            
        # Define EMAs for the price chart
        apds = [
            # EMA 20 and 50 on price chart
            mpf.make_addplot(df['ema20'], color=self.colors['ema20'], width=1.5),
            mpf.make_addplot(df['ema50'], color=self.colors['ema50'], width=1.5),
            
            # RSI in panel 1
            mpf.make_addplot(df['rsi'], panel=1, color=self.colors['rsi'], width=1.5,
                            ylabel='RSI (14)', secondary_y=False),
                            
            # MACD and signal in panel 2
            mpf.make_addplot(df['macd'], panel=2, color=self.colors['macd'], width=1.5,
                           secondary_y=False),
            mpf.make_addplot(df['macd_signal'], panel=2, color=self.colors['macd_signal'], width=1.5,
                           secondary_y=False)
        ]
        
        # Add the MACD histogram with correct coloring (green for positive, red for negative)
        macd_hist_colors = [self.colors['macd_hist_up'] if val > 0 else self.colors['macd_hist_down']
                          for val in df['macd_hist']]
        apds.append(mpf.make_addplot(df['macd_hist'], type='bar', panel=2, color=macd_hist_colors, alpha=0.5,
                                  secondary_y=False))
        
        # Additional customizations through kwarg dict
        plot_kwargs = {
            'type': 'candle',
            'style': self.style,
            'title': title,
            'figsize': (self.fig_width, self.fig_height),
            'panel_ratios': (6, 2, 2),  # Main chart, RSI, MACD
            'addplot': apds,
            'volume': True,
            'ylabel': f'Price ({display_symbol})',
            'datetime_format': '%m-%d %H:%M',
            'tight_layout': True,
            'scale_padding': {'left': 0.1, 'right': 1.1, 'top': 0.8, 'bottom': 0.8}
        }
        
        # Create a BytesIO object to save the chart to
        buf = io.BytesIO()
        
        # Create the figure first manually
        fig, axes = mpf.plot(df, **plot_kwargs, returnfig=True)
        
        # Get the axes objects
        ax_main = axes[0]  # Main price chart
        ax_rsi = axes[2]   # RSI panel 
        ax_macd = axes[3]  # MACD panel
        
        # Manually add horizontal lines on RSI panel
        ax_rsi.axhline(y=30, color=self.colors['rsi_os'], linestyle='--', alpha=0.5)
        ax_rsi.axhline(y=70, color=self.colors['rsi_ob'], linestyle='--', alpha=0.5)
        
        # Add horizontal line at zero for MACD panel
        ax_macd.axhline(y=0, color=self.colors['grid'], linestyle='-', alpha=0.3)
        
        # Add stop loss and take profit lines on main price chart if provided
        if stop_loss is not None:
            ax_main.axhline(y=stop_loss, color=self.colors['sl'], linestyle='--', 
                         alpha=0.7, linewidth=1.5, label='Stop Loss')
        
        if take_profit is not None:
            ax_main.axhline(y=take_profit, color=self.colors['tp'], linestyle='--', 
                         alpha=0.7, linewidth=1.5, label='Take Profit')
        
        # Add legend for price chart
        handles, labels = ax_main.get_legend_handles_labels()
        if handles:
            ax_main.legend(loc='upper left', framealpha=0.5)
        
        # Save the figure to BytesIO buffer
        fig.savefig(buf, format='png', dpi=self.dpi, bbox_inches='tight')
        plt.close(fig)  # Close the figure to free memory
        
        # Reset buffer position and return bytes
        buf.seek(0)
        return buf.getvalue()