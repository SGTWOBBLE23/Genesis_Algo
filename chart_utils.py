import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib import rcParams
import pandas as pd

from oanda_api import OandaAPI
from chart_generator_basic import ChartGenerator  # single import is enough
from config import mt5_to_oanda

# ──────────────────────────────────────────────────────────────
#  Indicator helpers
# ──────────────────────────────────────────────────────────────
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add EMA-20/50/200, RSI-14, and MACD(12,26,9) columns to *df* in-place
    and return the same DataFrame.
    """
    close = df["close"]

    # EMAs
    df["ema20"]  = close.ewm(span=20,  adjust=False).mean()
    df["ema50"]  = close.ewm(span=50,  adjust=False).mean()
    df["ema200"] = close.ewm(span=200, adjust=False).mean()

    # RSI-14
    delta = close.diff()
    up   = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    roll_up   = up.ewm(span=14, adjust=False).mean()
    roll_down = down.ewm(span=14, adjust=False).mean()
    rs = roll_up / (roll_down + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    df["macd"]      = macd
    df["macd_sig"]  = signal
    df["macd_hist"] = macd - signal
    return df


# ──────────────────────────────────────────────────────────────
#  Matplotlib light theme
# ──────────────────────────────────────────────────────────────
plt.style.use("seaborn-v0_8-white")
rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor":   "white",
    "grid.color":       "#D0D0D0",
    "grid.alpha":       0.4,
    "text.color":       "#111111",
    "axes.labelcolor":  "#111111",
    "xtick.color":      "#111111",
    "ytick.color":      "#111111",
    "font.size":        11,
})


# ──────────────────────────────────────────────────────────────
#  Logging & OANDA client
# ──────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

oanda_api = OandaAPI(
    api_key=os.environ.get("OANDA_API_KEY"),
    account_id=os.environ.get("OANDA_ACCOUNT_ID"),
)


# ──────────────────────────────────────────────────────────────
#  Candle fetching
# ──────────────────────────────────────────────────────────────
def fetch_candles(
    symbol: str,
    timeframe: str = "H1",
    count: int = 300,
    **params,                       # ← allows “to=…”, “from=…”, etc.
) -> List[Dict]:
    """
    Fetch *count* candles from OANDA and return them as a list of dicts.
    Extra query-string keys can be supplied via **params.
    """
    if "_" not in symbol:
        symbol = mt5_to_oanda(symbol)
    try:
        candles = oanda_api.get_candles(symbol, timeframe, count, **params)

        if not candles:
            logger.error("Error fetching candles for %s: No data returned", symbol)
            return []

        if isinstance(candles, dict) and candles.get("error"):
            logger.error("Error fetching candles for %s: %s", symbol, candles["error"])
            return []

        return candles
    except Exception as exc:                         # broad catch keeps pipeline alive
        logger.error("Exception fetching candles for %s: %s", symbol, exc)
        return []


# ──────────────────────────────────────────────────────────────
#  Chart generation helpers
# ──────────────────────────────────────────────────────────────
def generate_chart(
    symbol: str,
    timeframe: str = "H1",
    count: int = 300,
    entry_point: Optional[Tuple[datetime, float]] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    result: Optional[str] = None,
    signal_action: Optional[str] = None,
) -> str:
    """
    Build a PNG chart (with optional trade annotations) and return its file path.
    """
    logger.info(
        "Generating enhanced chart for %s (%s) with %d candles",
        symbol, timeframe, count,
    )

    candles = fetch_candles(symbol, timeframe, count)
    if not candles:
        return ""

    chart_gen = ChartGenerator(signal_action=signal_action)
    return chart_gen.create_chart(
        candles=candles,
        symbol=symbol,
        timeframe=timeframe,
        entry_point=entry_point,
        stop_loss=stop_loss,
        take_profit=take_profit,
        result=result,
    )


def generate_chart_bytes(
    symbol: str,
    timeframe: str = "H1",
    count: int = 300,
    entry_point: Optional[Tuple[datetime, float]] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    result: Optional[str] = None,
    signal_action: Optional[str] = None,
) -> bytes:
    """
    Same as *generate_chart* but returns raw bytes instead of writing to disk.
    """
    logger.info(
        "Generating chart bytes for %s (%s) with %d candles",
        symbol, timeframe, count,
    )

    candles = fetch_candles(symbol, timeframe, count)
    if not candles:
        return b""

    chart_gen = ChartGenerator(signal_action=signal_action)
    return chart_gen.create_chart_bytes(
        candles=candles,
        symbol=symbol,
        timeframe=timeframe,
        entry_point=entry_point,
        stop_loss=stop_loss,
        take_profit=take_profit,
        result=result,
    )


# ──────────────────────────────────────────────────────────────
#  “10-pip tolerance” helpers
# ──────────────────────────────────────────────────────────────
def pip_tolerance(symbol: str) -> float:
    """
    ≈10 pips expressed in the instrument’s quote units.

        • Metals (XAU/XAG) → 0.20  
        • JPY pairs        → 0.02  
        • 5-dp majors      → 0.0002
    """
    if symbol.startswith(("XAU", "XAG")):
        return 0.20
    if symbol.endswith("JPY"):
        return 0.02
    return 0.0002


def is_price_too_close(symbol: str, price_a: float, price_b: float) -> bool:
    """True if the two prices sit inside the instrument’s 10-pip band."""
    return abs(price_a - price_b) <= pip_tolerance(symbol)
