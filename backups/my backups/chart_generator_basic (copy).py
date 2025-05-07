import os
import io
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from matplotlib.gridspec import GridSpec
import matplotlib.dates as mdates

# Import mplfinance for candlestick charts
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import ConciseDateFormatter        # ⬅ new
from matplotlib.gridspec import GridSpec                  # ⬅ new
import mplfinance as mpf
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChartGenerator:
    """Class for generating technical analysis charts with indicators using mplfinance"""
    
    def __init__(self, signal_action=None):
        # Configure matplotlib for non-interactive backend
        plt.switch_backend('agg')
        
        # Default chart size - high resolution for clear ChatGPT Vision analysis
        # Updated to 1080p (19.2 x 10.8) for better legibility
        self.fig_width = 19.2
        self.fig_height = 14.4
        self.dpi = 100  # 1920x1080 resolution
        
        # Store signal action for positioning marker appropriately
        self.current_signal_action = signal_action
        logger.info(f"Initializing chart generator with signal action: {signal_action}")
        
        # Output directory for saving charts
        self.output_dir = os.path.join('static', 'charts')
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Using chart output directory: {os.path.abspath(self.output_dir)}")
        
        # Light theme colors for mplfinance with improved readability
        self.colors = {
            'bg': '#ffffff',            # White background for better readability
            'text': '#111111',          # Dark text for contrast
            'grid': '#D0D0D0',          # Light grey grid lines
            'candle_up': '#0E8B5C',     # Darker green for bullish candles
            'candle_down': '#D2384A',   # Darker red for bearish candles
            'ema20': '#0072EC',         # Darker blue for EMA 20 - better contrast
            'ema50': '#EB7200',         # Darker orange for EMA 50 - better contrast
            'volume': '#A0A0A0',        # Grey volume bars
            'volume_up': '#0E8B5C',     # Green up volume
            'volume_down': '#D2384A',   # Red down volume
            'rsi': '#0072EC',           # Blue RSI line
            'rsi_ob': '#D2384A',        # Red overbought line
            'rsi_os': '#0E8B5C',        # Green oversold line
            'macd': '#0072EC',          # Blue MACD line
            'macd_signal': '#EB7200',   # Orange signal line
            'macd_hist_up': '#0E8B5C',  # Green histogram up
            'macd_hist_down': '#D2384A',# Red histogram down
            'buy_entry': '#00BB00',     # Green arrow for buy entry
            'sell_entry': '#DD0000',    # Red arrow for sell entry
            'sl': '#DD0000',            # Red line for stop loss
            'tp': '#00BB00',            # Green line for take profit
            'atr': '#9B30FF'            # Purple for ATR line
        }
        
        # No need for a second directory definition - we already set self.output_dir above
    
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
        
        # Ensure Volume data exists
        if 'Volume' not in df.columns or df['Volume'].isnull().all():
            logger.info(f"Volume data not found or all null, adding synthetic volume")
            # Create synthetic volume based on price movement (for visualization purposes)
            df['Volume'] = abs(df['Close'] - df['Open']) * 100
            df['Volume'] = df['Volume'].fillna(1)  # Fill any NaN values
        
        # Add a log entry to verify data
        if not df.empty:
            latest_time = df['datetime'].iloc[-1] if 'datetime' in df else None
            latest_price = df['Close'].iloc[-1] if 'Close' in df else None
            logging.info(f"Latest candle data: time={latest_time}, close price={latest_price}")
        
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
            Path to saved chart image in format SYMBOL_TIMEFRAME_TIMESTAMP_RESULT.png
        """
        try:
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
                
            # Create a figure with subplots for price chart, volume, RSI, MACD, and ATR
            # Updated height ratios to make price chart much larger relative to indicators
            fig, axes = plt.subplots(5, 1, figsize=(self.fig_width, self.fig_height), 
                                   gridspec_kw={'height_ratios': [8, 1, 1.5, 1.5, 1]})
            for ax in axes:                            # axes = [price_ax, vol_ax, ...]
                ax.tick_params(axis='x',
                               labelsize=8,            # smaller font
                               pad=2,                  # pull ticks closer to frame
                               rotation=0)

            plt.subplots_adjust(hspace=0.07)           # reduce vertical gaps
            
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
            up = df['Close'] > df['Open']
            down = df['Close'] <= df['Open']
            
            # Plot candlestick wicks with increased line width
            axes[0].vlines(df.index[up], df['Low'][up], df['High'][up], color=self.colors['candle_up'], linewidth=1.5)
            axes[0].vlines(df.index[down], df['Low'][down], df['High'][down], color=self.colors['candle_down'], linewidth=1.5)
            
            # Plot candlestick bodies - increased width for better readability
            width = 0.8  # width of candlestick body - increased from 0.6
            for i, (idx, row) in enumerate(df.iterrows()):
                if row['Close'] > row['Open']:
                    # Bullish candle
                    rect = plt.Rectangle((i - width/2, row['Open']), width, row['Close'] - row['Open'],
                                      fill=True, color=self.colors['candle_up'])
                    axes[0].add_patch(rect)
                else:
                    # Bearish candle
                    rect = plt.Rectangle((i - width/2, row['Close']), width, row['Open'] - row['Close'],
                                      fill=True, color=self.colors['candle_down'])
                    axes[0].add_patch(rect)
            
            # Plot EMAs on main chart with increased line width
            axes[0].plot(np.arange(len(df)), df['ema20'], color=self.colors['ema20'], linewidth=2.0, label='EMA 20')
            axes[0].plot(np.arange(len(df)), df['ema50'], color=self.colors['ema50'], linewidth=2.0, label='EMA 50')
            
            # Add stop loss and take profit lines if provided
            if stop_loss is not None:
                axes[0].axhline(y=stop_loss, color=self.colors['sl'], linestyle='--', linewidth=1.5, label='Stop Loss')
            
            if take_profit is not None:
                axes[0].axhline(y=take_profit, color=self.colors['tp'], linestyle='--', linewidth=1.5, label='Take Profit')
            
            # ---------- explicit numeric overlays ----------
            last_close = df['Close'].iloc[-1]
            ema20_val  = df['ema20'].iloc[-1]
            ema50_val  = df['ema50'].iloc[-1]
            
            # Update legend to include values
            plt.legend([
                f"EMA 20  {ema20_val:.2f}",
                f"EMA 50  {ema50_val:.2f}",
                "Stop Loss",
                "Take Profit"
            ], loc="upper left", fontsize=9)
            
            # Large label for current close
            axes[0].annotate(
                f"Close {last_close:.2f}",
                xy=(len(df)-1, last_close),
                xytext=(15, 0), textcoords="offset points",
                ha="left", va="center",
                fontsize=10, weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#111111")
            )
            
            # Set labels
            axes[0].set_ylabel('Price', color=self.colors['text'])
            
            # Plot volume on the second panel with colored bars matching candle colors
            for i, (idx, row) in enumerate(df.iterrows()):
                if i >= len(df) or 'Volume' not in df or pd.isna(df['Volume'].iloc[i]):
                    continue
                    
                vol_val = df['Volume'].iloc[i]
                # Use the same color as the candlestick (green for up, red for down)
                if i > 0 and 'Close' in df and 'Open' in df:
                    if df['Close'].iloc[i] > df['Open'].iloc[i]:
                        # Bullish volume
                        axes[1].bar(i, vol_val, width=0.8, color=self.colors['candle_up'], alpha=0.8)
                    else:
                        # Bearish volume
                        axes[1].bar(i, vol_val, width=0.8, color=self.colors['candle_down'], alpha=0.8)
                else:
                    # Default color if we can't determine direction
                    axes[1].bar(i, vol_val, width=0.8, color='gray', alpha=0.5)
            
            axes[1].set_ylabel('Volume', color=self.colors['text'], fontsize=10)
            
            # Plot RSI on the third panel
            axes[2].plot(np.arange(len(df)), df['rsi'], color=self.colors['rsi'], linewidth=1.5)
            axes[2].axhline(y=30, color=self.colors['rsi_os'], linestyle='--')
            axes[2].axhline(y=70, color=self.colors['rsi_ob'], linestyle='--')
            axes[2].set_ylim(0, 100)
            
            # Add RSI value label
            rsi_val = df['rsi'].iloc[-1]
            axes[2].annotate(
                f"RSI: {rsi_val:.1f}",
                xy=(len(df)-1, rsi_val),
                xytext=(15, 0), textcoords="offset points",
                ha="left", va="center",
                fontsize=10, weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#111111")
            )
            
            axes[2].set_ylabel('RSI (14)', color=self.colors['text'], fontsize=10)
            
            # Plot MACD on the fourth panel
            axes[3].plot(np.arange(len(df)), df['macd'], color=self.colors['macd'], linewidth=1.5, label='MACD')
            axes[3].plot(np.arange(len(df)), df['macd_signal'], color=self.colors['macd_signal'], linewidth=1.5, label='Signal')
            axes[3].axhline(y=0, color=self.colors['grid'], linestyle='-')
            
            # Add MACD histogram bars
            for i, (idx, row) in enumerate(df.iterrows()):
                if i >= len(df['macd_hist']):
                    continue
                hist_val = df['macd_hist'].iloc[i]
                if hist_val >= 0:
                    # Positive histogram
                    axes[3].bar(i, hist_val, width=0.8, color=self.colors['macd_hist_up'], alpha=0.5)
                else:
                    # Negative histogram
                    axes[3].bar(i, hist_val, width=0.8, color=self.colors['macd_hist_down'], alpha=0.5)
            
            # Add MACD value labels
            macd_val = df['macd'].iloc[-1]
            signal_val = df['macd_signal'].iloc[-1]
            hist_val = df['macd_hist'].iloc[-1]
            
            # Create legend with current values
            axes[3].legend(
                [f"MACD: {macd_val:.4f}", f"Signal: {signal_val:.4f}", f"Hist: {hist_val:.4f}"],
                loc='upper left', fontsize=10
            )
            
            axes[3].set_ylabel('MACD (12,26,9)', color=self.colors['text'], fontsize=10)
            
            # Plot ATR as a thin line in the fifth panel
            axes[4].plot(np.arange(len(df)), df['atr'], color=self.colors['atr'], linewidth=1.5)
            
            # Add ATR value label
            atr_val = df['atr'].iloc[-1]
            axes[4].annotate(
                f"ATR: {atr_val:.5f}",
                xy=(len(df)-1, atr_val),
                xytext=(15, 0), textcoords="offset points",
                ha="left", va="center",
                fontsize=10, weight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#111111")
            )
            
            axes[4].set_ylabel('ATR (14)', color=self.colors['text'], fontsize=10)
            
            # Set x-axis labels for all chart panels
            x_positions = np.linspace(0, len(df) - 1, min(10, len(df)))
            x_labels = [df.index[int(pos)].strftime('%Y-%m-%d %H:%M') for pos in x_positions]
            
            # Apply x-axis labels to all charts
            for ax in axes:
                ax.set_xticks(x_positions)
                ax.set_xticklabels(x_labels, rotation=45)
            
            # Set x-axis ranges with extra space on the right for future price movement
            chart_padding = int(len(df) * 0.15)  # Add 15% padding to the right
            for ax in axes:
                ax.set_xlim(0, len(df) + chart_padding)
                
            # Adjust y-axis in main chart to better show SL and TP levels
            if stop_loss is not None or take_profit is not None:
                current_price = df['Close'].iloc[-1] if not df.empty else None
                if current_price:
                    # Get current y-limits
                    ymin, ymax = axes[0].get_ylim()
                    price_range = ymax - ymin
                    
                    # Determine required y range to show TP/SL properly
                    required_ymin = ymin
                    required_ymax = ymax
                    
                    if stop_loss is not None:
                        required_ymin = min(required_ymin, stop_loss - (price_range * 0.1))
                        required_ymax = max(required_ymax, stop_loss + (price_range * 0.1))
                    
                    if take_profit is not None:
                        required_ymin = min(required_ymin, take_profit - (price_range * 0.1))
                        required_ymax = max(required_ymax, take_profit + (price_range * 0.1))
                    
                    # Set new y-limits with a bit of padding
                    axes[0].set_ylim(required_ymin, required_ymax)
            
            # Add spacing between subplots
            plt.tight_layout()
            
            # Add entry point marker if provided
            if entry_point is not None:
                entry_time, entry_price = entry_point
                
                # For immediate signals (BUY_NOW/SELL_NOW), place entry at right edge
                # otherwise try to find the actual time for anticipated signals
                chart_right_edge = len(df) - 1  # Last candle index
                
                # Try to determine if this is a 'NOW' type signal from context
                is_immediate_signal = False
                if hasattr(self, 'current_signal_action'):
                    is_immediate_signal = 'NOW' in self.current_signal_action
                
                if is_immediate_signal:
                    # For immediate signals, place at right edge
                    entry_idx = chart_right_edge
                    logger.info(f"Placing immediate signal marker at right edge (index {entry_idx})")
                elif entry_time in df.index:
                    # For anticipated signals, place at the actual time if found
                    entry_idx = df.index.get_loc(entry_time)
                    logger.info(f"Placing anticipated signal marker at time {entry_time} (index {entry_idx})")
                else:
                    # If time not found, place it at last candle
                    entry_idx = chart_right_edge
                    logger.info(f"Time {entry_time} not found, placing marker at right edge (index {entry_idx})")
                
                # Plot arrow marker for entry point (different colors for buy/sell)
                marker_color = self.colors['buy_entry']  # Green arrow for buy signals
                marker_type = '^'  # Up arrow for buy signals
                
                # Determine if this is a sell/short signal
                is_sell_signal = False
                if hasattr(self, 'current_signal_action') and self.current_signal_action:
                    if 'SHORT' in self.current_signal_action or 'SELL' in self.current_signal_action:
                        is_sell_signal = True
                
                if is_sell_signal:
                    marker_color = self.colors['sell_entry']  # Red arrow for sell signals
                    marker_type = 'v'  # Down arrow for sell signals
                
                # Make entry marker larger and more visible
                axes[0].scatter(entry_idx, entry_price, marker=marker_type, s=200, 
                             color=marker_color, zorder=5, linewidth=2, edgecolor='white')
                    
            # Create symbol folder if it doesn't exist
            # Clean up symbol name for directory (remove underscores)
            clean_symbol = symbol.replace('_', '')
            symbol_dir = os.path.join(self.output_dir, clean_symbol)
            os.makedirs(symbol_dir, exist_ok=True)
            
            logger.info(f"Chart will be saved in directory: {os.path.abspath(symbol_dir)}")
            
            # Generate timestamp for filename with current date
            current_datetime = datetime.now()
            now = current_datetime.strftime("%Y%m%d_%H%M%S")
            result_str = f"_{result.lower()}" if result else ""
            # Format: SYMBOL_TIMEFRAME_TIMESTAMP_RESULT.png
            filename = f"{clean_symbol}_{timeframe}_{now}{result_str}.png"
            filepath = os.path.join(symbol_dir, filename)
            
            logger.info(f"Chart will be saved as: {filename}")
            
            # Update the chart title to include symbol, timeframe, result and current date
            display_symbol = symbol.replace("_", "/")
            title_text = f"{display_symbol} ({timeframe})"
            if result:
                title_text += f" - {result.upper()}"
            title_text += f" - {current_datetime.strftime('%Y-%m-%d')}"
            # Add ATR value
            latest_atr = df['atr'].iloc[-1] if not df['atr'].empty else 0
            title_text += f" - ATR(14): {latest_atr:.5f}"
            
            fig.suptitle(title_text, color=self.colors['text'], fontsize=14)
            
            # Save the chart to file
            plt.savefig(filepath, dpi=self.dpi, bbox_inches='tight', facecolor=self.colors['bg'], edgecolor='none')
            plt.close(fig)  # Close the figure to free memory
            
            logger.info(f"Chart saved to {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error creating chart: {str(e)}")
            return ""
    
    def create_chart_bytes(self, candles: List[Dict], symbol: str, timeframe: str,
                         entry_point: Optional[Tuple[datetime, float]] = None,
                         stop_loss: Optional[float] = None,
                         take_profit: Optional[float] = None,
                         result: Optional[str] = None) -> bytes:
        """Create chart and return as bytes for in-memory processing
        
        This is useful for directly sending charts via API without saving to disk
        """
        try:
            filepath = self.create_chart(candles, symbol, timeframe, entry_point, stop_loss, take_profit, result)
            
            if not filepath:
                return b""
                
            # Read the file as bytes
            with open(filepath, 'rb') as f:
                chart_bytes = f.read()
                
            return chart_bytes
        
        except Exception as e:
            logger.error(f"Error creating chart bytes: {str(e)}")
            return b""