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
from position_manager import PositionManager
from chart_utils import compute_indicators
from capture_job import yield_candles

logger = logging.getLogger(__name__)

# ------------------------------------------------------------
#  Back-test runner
# ------------------------------------------------------------
def run(
    symbol: str,
    tf: str = "M15",
    start: datetime | None = None,
    end: datetime | None = None,
):
    if start is None:
        start = datetime.utcnow() - timedelta(days=60)
    if end is None:
        end = datetime.utcnow()

    pm = PositionManager()
    next_ticket = 1  # fake ticket counter for back-test

    for candle in yield_candles(symbol, tf, start, end):
        close_price = candle["close"]
        high_price  = candle["high"]
        low_price   = candle["low"]
        atr_value   = candle.get("atr") or abs(high_price - low_price)

        # -------- entry signal (very simple example) -----------------
        df        = compute_indicators(pd.DataFrame([candle]))
        ml_prob   = predict_one(symbol, tf, df.iloc[-1])
        tech_score = 1.0
        score      = tech_score * ml_prob

        if score > 0.60:
            pm.open(
                symbol=symbol,
                price=close_price,
                atr=atr_value,
                tf=tf,
                feature_dict=df.iloc[-1].to_dict(),  # for RR model
                ticket_id=next_ticket,               # dummy ticket
            )
            next_ticket += 1

        # -------- bar-by-bar management ------------------------------
        pm.update_prices(
            price=close_price,
            high=high_price,
            low=low_price,
            atr=atr_value,
        )

    print("Final equity curve:", pm.equity_curve)

# ------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD")
    parser.add_argument("--tf",     default="M15")
    args = parser.parse_args()
    run(args.symbol, args.tf)
