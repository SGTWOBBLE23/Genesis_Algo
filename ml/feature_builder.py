#!/usr/bin/env python3
"""
Feature-builder for GENESIS ML layer

Builds a numeric feature DataFrame per candle that lines up with the
columns expected by the XGBoost models:

    open  high  low  close  volume
    ema20  ema50  ema200
    rsi
    macd  macd_sig  macd_hist
"""

from __future__ import annotations

import logging
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Primary entry-point
# ──────────────────────────────────────────────────────────────
def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Accepts a raw OHLC[V] DataFrame and returns one with
    all numeric columns in the exact order required by the
    inference models.

    Missing fields (like volume on some FX feeds) are filled
    with zeros so the column exists.
    """
    # --- Ensure required base columns exist
    base_cols = ["open", "high", "low", "close"]
    for col in base_cols:
        if col not in df.columns:
            raise ValueError(f"Input frame missing {col}")

    # Add volume if absent
    if "volume" not in df.columns:
        df["volume"] = 0.0

    # --- Indicators ---------------------------------------------------------
    # EMAs
    df["ema20"]  = df["close"].ewm(span=20,  adjust=False).mean()
    df["ema50"]  = df["close"].ewm(span=50,  adjust=False).mean()
    df["ema200"] = df["close"].ewm(span=200, adjust=False).mean()

    # RSI (14)
    delta = df["close"].diff()
    up    = delta.clip(lower=0)
    down  = -delta.clip(upper=0)
    roll_up   = up.rolling(14).mean()
    roll_down = down.rolling(14).mean()
    rs  = roll_up / (roll_down + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD (12-26-9)
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_sig"]  = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]

    # If old columns exist, drop them to avoid duplicate names
    df = df.drop(columns=[c for c in ["signal", "histogram"] if c in df.columns])

    # --- Final column order
    final_cols = [
        "open", "high", "low", "close", "volume",
        "ema20", "ema50", "ema200",
        "rsi",
        "macd", "macd_sig", "macd_hist"
    ]
    df = df[final_cols]

    # Replace any NaN from initial EMA/RSI warm-up with 0
    df = df.fillna(0.0).astype("float32")

    logger.debug("Built features frame with shape %s", df.shape)
    return df
