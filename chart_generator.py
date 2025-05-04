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
from matplotlib.patches import Rectangle
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
    
    def _prepare_data(self, candles: List[Dict], symbol: str, timeframe: str) -> pd.DataFrame:
        """Process candle data into a pandas DataFrame and add indicators
        
        Args:
            candles: List of candle dictionaries from OANDA API
            symbol: Trading symbol/instrument name
            timeframe: Chart timeframe (e.g., "H1")
            
        Returns:
            DataFrame with OHLCV data and indicators
        """
        # Create DataFrame
        df = pd.DataFrame(candles)
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Rename columns to standard names
        df = df.rename(columns={
            'timestamp': 'datetime',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        # Set datetime as index
        df = df.set_index('datetime')
        
        # Calculate indicators
        # EMA 20 and 50
        df['ema20'] = self._ema(df['close'], 20)
        df['ema50'] = self._ema(df['close'], 50)
        
        # RSI-14
        df['rsi'] = self._rsi(df['close'], 14)
        
        # MACD (12, 26, 9)
        macd_data = self._macd(df['close'], 12, 26, 9)
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['macd_signal']
        df['macd_hist'] = macd_data['macd_hist']
        
        # ATR-14
        df['atr'] = self._atr(df['high'], df['low'], df['close'], 14)
        
        # Return the DataFrame with all indicators calculated
        return df
    
    def _plot_candlestick_chart(self, df: pd.DataFrame, ax: plt.Axes, symbol: str, timeframe: str,
                               show_ema: bool = True) -> None:
        """Plot candlestick chart with EMAs"""
        # Plot candlesticks
        width = 0.6  # width of candlestick body
        width2 = 0.05  # width of wicks
        
        # Uptrend vs downtrend colors for candles
        up = df['close'] > df['open']
        down = df['close'] <= df['open']
        
        # Plot candle wicks
        ax.vlines(df.index[up], df['low'][up], df['high'][up], 
                color=self.colors['candle_up'])
        ax.vlines(df.index[down], df['low'][down], df['high'][down], 
                color=self.colors['candle_down'])
        
        # Plot candle bodies
        rect_up = [Rectangle((date-pd.Timedelta(hours=width/2), open_),
                            width, close-open_)
                for date, open_, close in zip(df.index[up], df['open'][up], df['close'][up])]
        rect_down = [Rectangle((date-pd.Timedelta(hours=width/2), close),
                            width, open_-close)
                for date, open_, close in zip(df.index[down], df['open'][down], df['close'][down])]
        
        # Add candle bodies to the plot
        pcup = plt.matplotlib.collections.PatchCollection(rect_up, facecolor=self.colors['candle_up'],
                                                        edgecolor=self.colors['candle_up'])
        pcdown = plt.matplotlib.collections.PatchCollection(rect_down, facecolor=self.colors['candle_down'],
                                                          edgecolor=self.colors['candle_down'])
        ax.add_collection(pcup)
        ax.add_collection(pcdown)
        
        # Plot EMAs if requested
        if show_ema:
            ax.plot(df.index, df['ema20'], color=self.colors['ema20'], linewidth=1.5, label='EMA 20')
            ax.plot(df.index, df['ema50'], color=self.colors['ema50'], linewidth=1.5, label='EMA 50')
        
        # Set chart title with symbol, timeframe, and ATR value
        latest_atr = df['atr'].iloc[-1]
        title = f"{symbol} ({timeframe}) - ATR(14): {latest_atr:.5f}"
        ax.set_title(title, color=self.colors['text'], fontsize=14, loc='left')
        
        # Format axes
        ax.set_ylabel('Price', color=self.colors['text'])
        ax.grid(color=self.colors['grid'], linestyle='-', linewidth=0.5, alpha=0.5)
        ax.legend(framealpha=0.5, loc='upper left')
        
        # Format dates on x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')
    
    def _plot_rsi(self, df: pd.DataFrame, ax: plt.Axes) -> None:
        """Plot RSI indicator"""
        # Plot RSI line
        ax.plot(df.index, df['rsi'], color=self.colors['rsi'], linewidth=1.5)
        
        # Add overbought and oversold lines
        ax.axhline(70, color=self.colors['rsi_ob'], linestyle='--', alpha=0.5)
        ax.axhline(30, color=self.colors['rsi_os'], linestyle='--', alpha=0.5)
        
        # Set RSI range
        ax.set_ylim(0, 100)
        
        # Set labels and grid
        ax.set_ylabel('RSI (14)', color=self.colors['text'])
        ax.grid(color=self.colors['grid'], linestyle='-', linewidth=0.5, alpha=0.5)
        
        # Hide x-axis labels as they will be shown on the bottom panel
        ax.set_xticklabels([])
    
    def _plot_macd(self, df: pd.DataFrame, ax: plt.Axes) -> None:
        """Plot MACD indicator"""
        # Plot MACD and signal lines
        ax.plot(df.index, df['macd'], color=self.colors['macd'], linewidth=1.5, label='MACD')
        ax.plot(df.index, df['macd_signal'], color=self.colors['macd_signal'], linewidth=1.5, label='Signal')
        
        # Plot histogram with colors based on value
        pos = df['macd_hist'] > 0
        neg = df['macd_hist'] <= 0
        
        # Plot positive and negative histogram bars with different colors
        ax.bar(df.index[pos], df['macd_hist'][pos], color=self.colors['macd_hist_up'], width=0.6, alpha=0.5)
        ax.bar(df.index[neg], df['macd_hist'][neg], color=self.colors['macd_hist_down'], width=0.6, alpha=0.5)
        
        # Add horizontal line at zero
        ax.axhline(0, color=self.colors['grid'], linestyle='-', alpha=0.3)
        
        # Set labels and grid
        ax.set_ylabel('MACD (12,26,9)', color=self.colors['text'])
        ax.grid(color=self.colors['grid'], linestyle='-', linewidth=0.5, alpha=0.5)
        ax.legend(framealpha=0.5, loc='upper left')
        
        # Format dates on x-axis (bottom panel)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha('right')
    
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
        
        # Create plot annotations
        annotations = []
        extra_plot_lines = []
        title_suffix = f"ATR(14): {latest_atr:.5f}"
        
        # Setup for result (win/loss) indicator
        title = f"{display_symbol} ({timeframe}) - {title_suffix}"
        if result:
            title = f"{display_symbol} ({timeframe}) - {result.upper()} - {title_suffix}"
        
        # Add entry point annotation
        if entry_point is not None:
            entry_time, entry_price = entry_point
            if isinstance(entry_time, str):
                entry_time = pd.to_datetime(entry_time)
                
            # Check if the entry time falls within our chart
            if entry_time in df.index or (df.index[0] <= entry_time <= df.index[-1]):
                # Create arrow annotation for entry
                annotations.append(
                    dict(
                        x=entry_time,
                        y=entry_price,
                        text='ENTRY',
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=2,
                        arrowcolor=self.colors['entry']
                    )
                )
        
        # Add horizontal lines for stop loss and take profit
        if stop_loss is not None:
            extra_plot_lines.append(
                dict(
                    y=stop_loss,
                    color=self.colors['sl'],
                    width=1.5,
                    alpha=0.7,
                    linestyle='dashed',
                    label='SL'
                )
            )
            
        if take_profit is not None:
            extra_plot_lines.append(
                dict(
                    y=take_profit,
                    color=self.colors['tp'],
                    width=1.5,
                    alpha=0.7,
                    linestyle='dashed',
                    label='TP'
                )
            )
        
        # Define EMAs to add to the plot
        emas = [
            mpf.make_addplot(df['ema20'], color=self.colors['ema20'], width=1.5, label='EMA 20'),
            mpf.make_addplot(df['ema50'], color=self.colors['ema50'], width=1.5, label='EMA 50')
        ]
        
        # Define RSI and MACD plots to add below the main chart
        add_plots = [
            # EMAs on price chart
            *emas,
            
            # RSI in panel 1
            mpf.make_addplot(df['rsi'], panel=1, color=self.colors['rsi'], width=1.5,
                             ylabel='RSI (14)', ylim=(0, 100)),
                             
            # MACD and signal lines in panel 2
            mpf.make_addplot(df['macd'], panel=2, color=self.colors['macd'], width=1.5, label='MACD'),
            mpf.make_addplot(df['macd_signal'], panel=2, color=self.colors['macd_signal'], width=1.5, label='Signal'),
        ]
        
        # Setup horizontal lines for RSI
        hlines = [
            dict(y=30, panel=1, color=self.colors['rsi_os'], linestyle='--', alpha=0.5),  # Oversold
            dict(y=70, panel=1, color=self.colors['rsi_ob'], linestyle='--', alpha=0.5),  # Overbought
        ]
        
        # Generate filename with timestamp
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_str = f"_{result.upper()}" if result else ""
        filename = f"{symbol}_{timeframe}_{now}{result_str}.png"
        filepath = os.path.join(self.output_dir, filename)
        
        # Create folder if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create the chart with mplfinance
        mpf.plot(
            df,
            type='candle',
            style=self.style,
            figsize=(self.fig_width, self.fig_height),
            title=title,
            addplot=add_plots,
            panel_ratios=(6, 2, 2),  # Main, RSI, MACD
            savefig=filepath,
            hlines=hlines,
            mav=(20, 50),  # Moving averages (just for the legend)
            volume=True,
            ylabel=f'Price ({display_symbol})',
            tight_layout=True,
            figratio=(16, 9),  # 16:9 aspect ratio (standard HD)
            figscale=1.5,     # Scale up for better quality
            warn_too_much_data=10000,  # Avoid warning for large datasets
        )
        
        logger.info(f"Chart saved to {filepath}")
        return filepath
            if entry_time in df.index:
                # Add entry arrow
                ax_candles.annotate('', xy=(entry_time, entry_price),
                                   xytext=(entry_time, entry_price - (df['atr'].iloc[-1] * 1.5)),
                                   arrowprops=dict(facecolor=self.colors['entry'], width=2),
                                   annotation_clip=True)
                
                # Add horizontal lines for stop-loss and take-profit if provided
                if stop_loss is not None:
                    ax_candles.axhline(stop_loss, color=self.colors['sl'], linestyle='-', linewidth=1.5)
                    ax_candles.text(df.index[-1], stop_loss, f'SL: {stop_loss:.5f}', 
                                  color=self.colors['sl'], ha='right', va='bottom')
                
                if take_profit is not None:
                    ax_candles.axhline(take_profit, color=self.colors['tp'], linestyle='-', linewidth=1.5)
                    ax_candles.text(df.index[-1], take_profit, f'TP: {take_profit:.5f}', 
                                  color=self.colors['tp'], ha='right', va='bottom')
        
        # Generate timestamp for filename
        now = datetime.now().strftime("%Y-%m-%dT%H%MZ")
        
        # Create filename using the requested format
        symbol_clean = symbol.replace("/", "").replace("_", "")
        result_suffix = f"_{result.lower()}" if result else ""
        filename = f"{symbol_clean}_{timeframe}_{now}{result_suffix}.png"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save the chart to file
        plt.savefig(filepath, bbox_inches='tight', facecolor=self.colors['bg'])
        plt.close(fig)
        
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
        df = self._prepare_data(candles, display_symbol, timeframe)
        
        # Create figure and subplots with specific heights
        fig = plt.figure(figsize=(self.fig_width, self.fig_height), dpi=self.dpi,
                         facecolor=self.colors['bg'])
        
        # Create subplots with specific height ratios
        gs = fig.add_gridspec(3, 1, height_ratios=[6, 2, 2], hspace=0.1)
        
        # Create axes for each subplot
        ax_candles = fig.add_subplot(gs[0])
        ax_rsi = fig.add_subplot(gs[1])
        ax_macd = fig.add_subplot(gs[2])
        
        # Set the facecolor for all axes
        for ax in [ax_candles, ax_rsi, ax_macd]:
            ax.set_facecolor(self.colors['bg'])
            
            # Set tick colors
            ax.tick_params(colors=self.colors['text'], which='both')
            ax.spines['bottom'].set_color(self.colors['grid'])
            ax.spines['top'].set_color(self.colors['grid'])
            ax.spines['left'].set_color(self.colors['grid'])
            ax.spines['right'].set_color(self.colors['grid'])
            
            # Set tick label color
            for label in ax.get_xticklabels() + ax.get_yticklabels():
                label.set_color(self.colors['text'])
        
        # Plot main chart with candlesticks and EMAs
        self._plot_candlestick_chart(df, ax_candles, display_symbol, timeframe, show_ema=True)
        
        # Plot RSI panel
        self._plot_rsi(df, ax_rsi)
        
        # Plot MACD panel
        self._plot_macd(df, ax_macd)
        
        # Add result label if provided
        if result:
            if result.lower() == 'win':
                label_color = self.colors['candle_up']  # green
            else:
                label_color = self.colors['candle_down']  # red
                
            plt.figtext(0.01, 0.98, result.upper(), fontsize=14, color=label_color, 
                        bbox=dict(facecolor=self.colors['bg'], alpha=0.6, edgecolor=label_color))
        
        # Add annotations if provided
        if entry_point is not None:
            entry_time, entry_price = entry_point
            # Find the nearest candle to the entry time
            if isinstance(entry_time, str):
                entry_time = pd.to_datetime(entry_time)
                
            # Check if the entry time is in the index
            if entry_time in df.index:
                # Add entry arrow
                ax_candles.annotate('', xy=(entry_time, entry_price),
                                   xytext=(entry_time, entry_price - (df['atr'].iloc[-1] * 1.5)),
                                   arrowprops=dict(facecolor=self.colors['entry'], width=2),
                                   annotation_clip=True)
                
                # Add horizontal lines for stop-loss and take-profit if provided
                if stop_loss is not None:
                    ax_candles.axhline(stop_loss, color=self.colors['sl'], linestyle='-', linewidth=1.5)
                    ax_candles.text(df.index[-1], stop_loss, f'SL: {stop_loss:.5f}', 
                                  color=self.colors['sl'], ha='right', va='bottom')
                
                if take_profit is not None:
                    ax_candles.axhline(take_profit, color=self.colors['tp'], linestyle='-', linewidth=1.5)
                    ax_candles.text(df.index[-1], take_profit, f'TP: {take_profit:.5f}', 
                                  color=self.colors['tp'], ha='right', va='bottom')
        
        # Save figure to bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', facecolor=self.colors['bg'])
        plt.close(fig)
        
        # Reset buffer position and return bytes
        buf.seek(0)
        return buf.getvalue()
