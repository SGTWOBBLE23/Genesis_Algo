
#!/usr/bin/env python3
"""
train_exit.py – Train per-symbol model to detect exit timing
-------------------------------------------------------------

Uses logs/trade_log.csv to replay closed trades and label each bar:

    1 = likely to hit TP
    0 = likely to hit SL

Trains XAUUSD_M15_exit.pkl, etc.

Run:
    python -m ml.train_exit --tf M15
"""

import argparse
import logging
import os
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from xgboost import XGBClassifier
from chart_utils import fetch_candles

# -------------------------
# Config
# -------------------------
ASSETS = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "GBPJPY", "BTCUSD"]
MODELS_DIR = Path(__file__).resolve().parent / "models"
MODELS_DIR.mkdir(exist_ok=True)
TRADE_LOG = Path("logs/trade_log.csv")

# -------------------------
# Helpers
# -------------------------
def extract_exit_training_rows(trade, candles, rr_hat: float) -> list[dict]:
    """Simulate bar-by-bar features and label for a single historical trade."""
    rows = []
    entry_time = pd.to_datetime(trade["timestamp"]).tz_localize("UTC")
    exit_time  = pd.to_datetime(trade["exit_time"]).tz_localize("UTC")
    df = candles[(candles.index >= entry_time) & (candles.index <= exit_time)].copy()
    if df.empty or len(df) < 3:
        return []

    sl, tp = trade["sl"], trade["tp"]
    side = "buy" if trade["action"] in ("BUY_NOW", "ANTICIPATED_LONG") else "sell"
    entry = trade["entry"]

    for i, (timestamp, row) in enumerate(df.iterrows()):
        price = row["close"]
        bars_open = i + 1
        atr = row["high"] - row["low"]
        rr_live = (tp - price) / (price - sl) if side == "buy" else (price - tp) / (sl - price)

        hit_tp = (row["high"] >= tp) if side == "buy" else (row["low"] <= tp)
        hit_sl = (row["low"] <= sl) if side == "buy" else (row["high"] >= sl)

        label = 1
        if hit_sl and not hit_tp:
            label = 0

        rows.append({
            "symbol": trade["symbol"],
            "bars_open": bars_open,
            "atr": atr,
            "range": row["high"] - row["low"],
            "session_hour": timestamp.hour,
            "entry_rr_hat": rr_hat,
            "unrealised_rr": rr_live,
            "label": label
        })

        if hit_tp or hit_sl:
            break

    return rows

def train_symbol(symbol: str, tf: str):
    logging.info("Training ExitNet for %s %s", symbol, tf)
    trades = pd.read_csv(TRADE_LOG, parse_dates=["timestamp", "exit_time"])
    trades = trades[(trades["symbol"] == symbol) & trades["exit_time"].notna()]

    candles = fetch_candles(symbol, tf, years=3)
    if isinstance(candles, list):
        candles = pd.DataFrame(candles)
    if "time" in candles.columns:
        candles["time"] = pd.to_datetime(candles["time"])
        candles = candles.set_index("time")

    rows = []
    for _, t in trades.iterrows():
        rr_hat = 1.5  # default if not stored
        rows.extend(extract_exit_training_rows(t, candles, rr_hat))

    if len(rows) < 100:
        logging.warning("Too few training rows for %s", symbol)
        return

    df = pd.DataFrame(rows).dropna()
    y = df.pop("label")
    X = df.drop(columns=["symbol"])

    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.07,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        random_state=42,
    )
    model.fit(X, y)

    out_path = MODELS_DIR / f"{symbol}_{tf}_exit.pkl"
    joblib.dump(model, out_path)
    logging.info("Saved %s", out_path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tf", required=True, help="Timeframe (M15, H1, etc.)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for symbol in ASSETS:
        train_symbol(symbol, args.tf)

if __name__ == "__main__":
    main()
