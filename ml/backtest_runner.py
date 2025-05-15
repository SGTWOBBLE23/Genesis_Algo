"""
Simple walk-forward back-tester that plugs SignalScorer and PositionManager
on historical candles.
"""
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from ml.model_inference import predict_one
from ml.exit_inference import predict_exit_prob            # optional, if you want ExitNet in BT
from signal_scoring import evaluate_signal                 # ← keep if you already implemented it
from position_manager import PositionManager
from config import ASSETS
from chart_utils import compute_indicators
from capture_job import yield_candles

logger = logging.getLogger(__name__)


def run(symbol: str,
        tf: str = "M15",
        start: datetime | None = None,
        end: datetime | None = None,):
    if start is None:
        start = datetime.utcnow() - timedelta(days=60)   # 60-day back-test default
    if end is None:
        end = datetime.utcnow()
    pm = PositionManager()
    for candle in yield_candles(symbol, tf, start, end):
        # candle is a dict with keys: time, open, high, low, close, volume, etc.
        close_price = candle["close"]
        high_price  = candle["high"]
        low_price   = candle["low"]
        atr_value   = candle.get("atr") or abs(high_price - low_price)  # fallback

        # ------------------------------------------------------------------
        # 1) ENTRY SIGNAL  (very simple example)
        # ------------------------------------------------------------------
        df = compute_indicators(pd.DataFrame([candle]))
        ml_prob    = predict_one(symbol, tf, df.iloc[-1])
        tech_score = 1.0                                              # placeholder
        score      = tech_score * ml_prob

        if score > 0.60:
            pm.open(
                symbol=symbol,
                price=close_price,
                atr=atr_value,
                tf=tf,                                               # tells Position its timeframe
            )

        # ------------------------------------------------------------------
        # 2) BAR-BY-BAR MANAGEMENT  (ExitNet + SL/TP + breakeven)
        # ------------------------------------------------------------------
        pm.update_prices(
            price=close_price,
            high=high_price,
            low=low_price,
            atr=atr_value,
        )

    print("Final equity curve:", pm.equity_curve)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--tf", default="M15")
    args = parser.parse_args()

    run(args.symbol, args.tf)
