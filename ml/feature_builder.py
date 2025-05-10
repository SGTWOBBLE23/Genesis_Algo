"""
Convert raw candle parquet files → feature parquet with indicators
Uses chart_utils.compute_indicators for consistency with live scoring.
"""
from pathlib import Path
import pandas as pd
from chart_utils import compute_indicators
from config import ASSETS

RAW_DIR = Path("data/raw")
FEAT_DIR = Path("data/features")
FEAT_DIR.mkdir(parents=True, exist_ok=True)

def build(symbol: str, tf: str = "M1"):
    files = sorted((RAW_DIR / symbol / tf).glob("*.parquet"))
    if not files:
        return
    df = pd.concat(pd.read_parquet(f) for f in files).reset_index(drop=True)
    df = compute_indicators(df)
    df.to_parquet(FEAT_DIR / f"{symbol}_{tf}.parquet")
