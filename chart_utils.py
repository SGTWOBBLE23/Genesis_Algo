import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

import matplotlib.pyplot as plt
from matplotlib import rcParams

from oanda_api import OandaAPI
from chart_generator_basic import ChartGenerator

# ---------- global light theme ----------
plt.style.use("seaborn-v0_8-white")
rcParams["figure.facecolor"] = "white"
rcParams["axes.facecolor"]   = "white"
rcParams["grid.color"]       = "#D0D0D0"
rcParams["grid.alpha"]       = 0.4
rcParams["text.color"]       = "#111111"
rcParams["axes.labelcolor"]  = "#111111"
rcParams["xtick.color"]      = "#111111"
rcParams["ytick.color"]      = "#111111"
rcParams["font.size"]        = 11              # bump base font


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Note: We'll create chart generators on-demand with appropriate signal_action parameters
# rather than having a global instance that doesn't know about signal types

# Initialize OANDA API client
oanda_api = OandaAPI(
    api_key=os.environ.get('OANDA_API_KEY'),
    account_id=os.environ.get('OANDA_ACCOUNT_ID')
)

def fetch_candles(symbol: str, timeframe: str = "H1", count: int = 300) -> List[Dict]:
    """Fetch candle data from OANDA API

    Args:
        symbol: Trading symbol/instrument name (e.g., "EUR_USD")
        timeframe: Chart timeframe (e.g., "H1", "M15", "D")
        count: Number of candles to retrieve

    Returns:
        List of candle dictionaries
    """
    try:
        # Request candles from OANDA
        candles = oanda_api.get_candles(symbol, timeframe, count)

        if not candles:
            logger.error(f"Error fetching candles for {symbol}: No data returned")
            return []

        if isinstance(candles, dict):
            error_msg = candles.get('error')
            if error_msg:
                logger.error(f"Error fetching candles for {symbol}: {error_msg}")
                return []

        return candles
    except Exception as e:
        logger.error(f"Exception fetching candles for {symbol}: {str(e)}")
        return []

def generate_chart(symbol: str, timeframe: str = "H1", count: int = 300, 
                  entry_point: Optional[Tuple[datetime, float]] = None,
                  stop_loss: Optional[float] = None, 
                  take_profit: Optional[float] = None,
                  result: Optional[str] = None,
                  signal_action: Optional[str] = None) -> str:
    """Generate chart for a symbol with optional trade annotations

    Args:
        symbol: Trading symbol/instrument name (e.g., "EUR_USD")
        timeframe: Chart timeframe (e.g., "H1", "M15", "D")
        count: Number of candles to retrieve
        entry_point: Optional tuple of (datetime, price) for entry annotation
        stop_loss: Optional price level for stop loss line
        take_profit: Optional price level for take profit line
        result: Optional trade result ("win" or "loss")
        signal_action: Optional signal action type (e.g., "BUY_NOW", "SELL_NOW", "ANTICIPATED_LONG", "ANTICIPATED_SHORT")
            affecting how entry points are positioned

    Returns:
        Path to saved chart image or empty string if error
    """
    logger.info(f"Generating enhanced chart for {symbol} ({timeframe}) with {count} candles")
    if signal_action:
        logger.info(f"Chart signal action: {signal_action}")
    if entry_point:
        logger.info(f"Entry point: time={entry_point[0]}, price={entry_point[1]}")
    if stop_loss:
        logger.info(f"Stop loss: {stop_loss}")
    if take_profit:
        logger.info(f"Take profit: {take_profit}")
    if result:
        logger.info(f"Trade result: {result}")
    try:
        # Fetch candles for the symbol
        candles = fetch_candles(symbol, timeframe, count)

        if not candles:
            logger.error(f"No candle data available for {symbol}")
            return ""

        # Create a chart generator with signal action
        from chart_generator_basic import ChartGenerator
        chart_gen = ChartGenerator(signal_action=signal_action)

        # Generate and save chart
        chart_path = chart_gen.create_chart(
            candles=candles,
            symbol=symbol,
            timeframe=timeframe,
            entry_point=entry_point,
            stop_loss=stop_loss,
            take_profit=take_profit,
            result=result
        )

        return chart_path
    except Exception as e:
        logger.error(f"Error generating chart for {symbol}: {str(e)}")
        return ""

def generate_chart_bytes(symbol: str, timeframe: str = "H1", count: int = 300, 
                       entry_point: Optional[Tuple[datetime, float]] = None,
                       stop_loss: Optional[float] = None, 
                       take_profit: Optional[float] = None,
                       result: Optional[str] = None,
                       signal_action: Optional[str] = None) -> bytes:
    """Generate chart for a symbol and return as bytes

    Args:
        symbol: Trading symbol/instrument name (e.g., "EUR_USD")
        timeframe: Chart timeframe (e.g., "H1", "M15", "D")
        count: Number of candles to retrieve
        entry_point: Optional tuple of (datetime, price) for entry annotation
        stop_loss: Optional price level for stop loss line
        take_profit: Optional price level for take profit line
        result: Optional trade result ("win" or "loss")
        signal_action: Optional signal action type (e.g., "BUY_NOW", "SELL_NOW", "ANTICIPATED_LONG", "ANTICIPATED_SHORT")
            affecting how entry points are positioned

    Returns:
        Chart as bytes or empty bytes if error
    """
    logger.info(f"Generating chart bytes for {symbol} ({timeframe}) with {count} candles")
    try:
        # Fetch candles for the symbol
        candles = fetch_candles(symbol, timeframe, count)

        if not candles:
            logger.error(f"No candle data available for {symbol}")
            return b""

        # Create a chart generator with signal action
        from chart_generator_basic import ChartGenerator
        chart_gen = ChartGenerator(signal_action=signal_action)

        # Generate chart as bytes
        chart_bytes = chart_gen.create_chart_bytes(
            candles=candles,
            symbol=symbol,
            timeframe=timeframe,
            entry_point=entry_point,
            stop_loss=stop_loss,
            take_profit=take_profit,
            result=result
        )

        return chart_bytes
    except Exception as e:
        logger.error(f"Error generating chart bytes for {symbol}: {str(e)}")
        return b""

# ────────────────────────────────────────────────────────────────
#  Shared “10-pip tolerance” helpers
# ────────────────────────────────────────────────────────────────
def pip_tolerance(symbol: str) -> float:
    """
    ≈10 pips expressed in the instrument’s quote units.

    • Metals (XAU/XAG) are quoted to 2 dp → 1.00  
    • JPY pairs are quoted to 3 dp     → 0.10  
    • Everything else (5-dp majors)    → 0.001
    """
    if symbol.startswith(("XAU", "XAG")):
        return 1.0
    if symbol.endswith("JPY"):
        return 0.10
    return 0.001


def is_price_too_close(symbol: str, price_a: float, price_b: float) -> bool:
    """True if the two prices sit inside the instrument’s 10-pip band."""
    return abs(price_a - price_b) <= pip_tolerance(symbol)