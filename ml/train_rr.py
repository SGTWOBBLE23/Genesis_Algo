
#!/usr/bin/env python3
"""train_rr.py – Train per‑symbol regression model to predict optimal
reward‑to‑risk (RR) for each trade entry.

How labels are derived
----------------------
For every historical entry row we compute:

    best_rr = max_favourable_excursion / max_adverse_excursion

…where excursions are measured in *price units* within a fixed
look‑ahead window (default 60 minutes).  If price never moves against
the entry before hitting TP, the adverse excursion is set to 1 tick.

The resulting `best_rr` becomes the regression target.

Usage
-----
$ python -m ml.train_rr --tf M5 --window 60

• Outputs «ml/models/{symbol}_{tf}_rr.pkl»
• Writes a CSV summary of feature importance per model.
"""
from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import List, Dict

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from chart_utils import fetch_candles, get_atr

# --------------------------------------------------
# Config
# --------------------------------------------------
THIS_DIR = Path(__file__).resolve().parent
MODELS_DIR = THIS_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)
ASSETS = [
    "XAUUSD", "EURUSD", "GBPUSD",
    "USDJPY", "GBPJPY", "BTCUSD"
]

# -----------------------------------------------
# Helpers
# -----------------------------------------------
def label_best_rr(df: pd.DataFrame, look_ahead: int = 60) -> pd.Series:
    """Return best achievable RR for each row.

    Assumes df has columns: open, high, low close
    """
    highs = df['high'].rolling(look_ahead, min_periods=1).max().shift(-look_ahead)
    lows  = df['low'] .rolling(look_ahead, min_periods=1).min().shift(-look_ahead)
    entry = df['open']
    # Favourable / adverse
    fav = np.where(df['side'] == 'buy', highs - entry, entry - lows)
    adv = np.where(df['side'] == 'buy', entry - lows, highs - entry)
    adv = np.where(adv == 0, 1e-6, adv)  # avoid divide‑by‑zero
    return fav / adv

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a minimal feature-set that mirrors what the live vision pipeline
    uses, plus a fast ATR computed locally (so we don’t need the API call).
    """
    # True-range vector
    high  = df["high"].to_numpy()
    low   = df["low"].to_numpy()
    close = df["close"].to_numpy()

    tr = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:]  - close[:-1]),
    ])
    # ATR-14 in price units (same length as df, pad first row)
    atr14 = pd.Series(np.r_[np.nan, tr]).ewm(span=14, adjust=False).mean()

    feats = pd.DataFrame({
        "atr":   atr14,
        "vwap":  (high + low + close) / 3,
        "range": high - low,
        "session_hour": df.index.hour,
    }, index=df.index)

    # Fill initial NaNs produced by the EMA
    feats = feats.bfill().ffill()
    return feats

# -----------------------------------------------
# Training loop
# -----------------------------------------------
def train_symbol(symbol: str, tf: str, window: int):
    logging.info("Training RR model for %s %s", symbol, tf)
    candles = fetch_candles(symbol, tf, years=3) 
    if isinstance(candles, list):
        candles = pd.DataFrame(candles)# 3‑yr history
    if not pd.api.types.is_datetime64_any_dtype(candles.index):
        if "timestamp" in candles.columns:
            candles["timestamp"] = pd.to_datetime(candles["timestamp"])
            candles = candles.set_index("timestamp")
        elif "time" in candles.columns:
            candles["time"] = pd.to_datetime(candles["time"])
            candles = candles.set_index("time")
    if candles.empty:
        logging.warning("No candles for %s – skipping", symbol)
        return
    candles['side'] = np.where(candles['close'] >= candles['open'], 'buy', 'sell')
    y = label_best_rr(candles, look_ahead=window)
    X = build_features(candles)

    model = XGBRegressor(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective='reg:squarederror',
        random_state=42
    )
    mask = np.isfinite(y) & np.isfinite(X).all(axis=1)
    X = X[mask]
    y = y[mask]
    model.fit(X, y)
    out_path = MODELS_DIR / f"{symbol}_{tf}_rr.pkl"
    joblib.dump(model, out_path)
    logging.info("Saved %s", out_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tf', default='M5', help='Timeframe e.g. M5')
    parser.add_argument('--window', type=int, default=60,
                        help='Look‑ahead in minutes for best RR')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    for sym in ASSETS:
        train_symbol(sym, args.tf, args.window)

if __name__ == '__main__':
    main()
