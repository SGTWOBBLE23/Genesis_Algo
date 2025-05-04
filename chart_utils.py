import os
import logging
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from oanda_api import OandaAPI
from chart_generator import ChartGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the chart generator
chart_generator = ChartGenerator()

# Initialize OANDA API client
oanda_api = OandaAPI(
    api_key=os.environ.get('OANDA_API_KEY'),
    account_id=os.environ.get('OANDA_ACCOUNT_ID')
)

def fetch_candles(symbol: str, timeframe: str = "H1", count: int = 100) -> List[Dict]:
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
        
        if isinstance(candles, dict) and 'error' in candles:
            logger.error(f"Error fetching candles for {symbol}: {candles['error']}")
            return []
        
        return candles
    except Exception as e:
        logger.error(f"Exception fetching candles for {symbol}: {str(e)}")
        return []

def generate_chart(symbol: str, timeframe: str = "H1", count: int = 100, 
                  entry_point: Optional[Tuple[datetime, float]] = None,
                  stop_loss: Optional[float] = None, 
                  take_profit: Optional[float] = None,
                  result: Optional[str] = None) -> str:
    """Generate chart for a symbol with optional trade annotations
    
    Args:
        symbol: Trading symbol/instrument name (e.g., "EUR_USD")
        timeframe: Chart timeframe (e.g., "H1", "M15", "D")
        count: Number of candles to retrieve
        entry_point: Optional tuple of (datetime, price) for entry annotation
        stop_loss: Optional price level for stop loss line
        take_profit: Optional price level for take profit line
        result: Optional trade result ("win" or "loss")
        
    Returns:
        Path to saved chart image or empty string if error
    """
    try:
        # Fetch candles for the symbol
        candles = fetch_candles(symbol, timeframe, count)
        
        if not candles:
            logger.error(f"No candle data available for {symbol}")
            return ""
        
        # Generate and save chart
        chart_path = chart_generator.create_chart(
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

def generate_chart_bytes(symbol: str, timeframe: str = "H1", count: int = 100, 
                       entry_point: Optional[Tuple[datetime, float]] = None,
                       stop_loss: Optional[float] = None, 
                       take_profit: Optional[float] = None,
                       result: Optional[str] = None) -> bytes:
    """Generate chart for a symbol and return as bytes
    
    Args:
        symbol: Trading symbol/instrument name (e.g., "EUR_USD")
        timeframe: Chart timeframe (e.g., "H1", "M15", "D")
        count: Number of candles to retrieve
        entry_point: Optional tuple of (datetime, price) for entry annotation
        stop_loss: Optional price level for stop loss line
        take_profit: Optional price level for take profit line
        result: Optional trade result ("win" or "loss")
        
    Returns:
        Chart as bytes or empty bytes if error
    """
    try:
        # Fetch candles for the symbol
        candles = fetch_candles(symbol, timeframe, count)
        
        if not candles:
            logger.error(f"No candle data available for {symbol}")
            return b""
        
        # Generate chart as bytes
        chart_bytes = chart_generator.create_chart_bytes(
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