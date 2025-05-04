import os
import io
import logging
import pandas as pd
import numpy as np
import pandas_ta as ta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle, Arrow
from matplotlib.lines import Line2D
from PIL import Image
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChartGenerator:
    """Class for generating technical analysis charts with indicators"""
    
    def __init__(self):
        # Configure matplotlib for non-interactive backend
        plt.switch_backend('agg')
        
        # Default chart size - high resolution for clear ChatGPT Vision analysis
        self.fig_width = 12.8
        self.fig_height = 7.2
        self.dpi = 100  # 1280x720 resolution
        
        # Default colors
        self.colors = {
            'bg': '#121826',
            'text': '#e0e0e0',
            'grid': '#2a2e39',
            'candle_up': '#26a69a',
            'candle_down': '#ef5350',
            'ema20': '#2962ff',  # blue
            'ema50': '#ff9800',  # orange
            'volume': '#2a2e39',
            'volume_up': '#26a69a',
            'volume_down': '#ef5350',
            'rsi': '#2962ff',
            'rsi_ob': '#ef5350',  # overbought
            'rsi_os': '#26a69a',  # oversold
            'macd': '#2962ff',
            'macd_signal': '#ff9800',
            'macd_hist_up': '#26a69a',
            'macd_hist_down': '#ef5350',
            'entry': '#00ff00',  # green arrow
            'sl': '#ff0000',     # red line (stop loss)
            'tp': '#00ff00'      # green line (take profit)
        }
        
        # Directory to save charts
        self.output_dir = os.path.join(os.getcwd(), 'static', 'charts')
        os.makedirs(self.output_dir, exist_ok=True)
    
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
        df['ema20'] = ta.ema(df['close'], length=20)
        df['ema50'] = ta.ema(df['close'], length=50)
        
        # RSI-14
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # MACD (12, 26, 9)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_hist'] = macd['MACDh_12_26_9']
        
        # ATR-14
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
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
    
    def create_chart(self, candles: List[Dict], symbol: str, timeframe: str,
                     entry_point: Optional[Tuple[datetime, float]] = None,
                     stop_loss: Optional[float] = None,
                     take_profit: Optional[float] = None,
                     result: Optional[str] = None) -> str:
        """Create a complete technical analysis chart with annotations
        
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
        df = self._prepare_data(candles, display_symbol, timeframe)
        
        # Create figure and subplots with specific heights
        fig = plt.figure(figsize=(self.fig_width, self.fig_height), dpi=self.dpi,
                         facecolor=self.colors['bg'])
        
        # Create subplots with specific height ratios
        gs = fig.add_gridspec(3, 1, height_ratios=[6, 2, 2], hspace=0.1)
        
        # Create axess for each subplot
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
