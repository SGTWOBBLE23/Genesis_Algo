"""
Simple walk‑forward back‑tester that plugs SignalScorer and PositionManager
on historical candles.
"""
import argparse, logging
from datetime import datetime
from pathlib import Path
import pandas as pd
from ml.model_inference import predict_one
from signal_scoring import evaluate_signal  # assuming such a function exists
from position_manager import PositionManager
from config import ASSETS
from chart_utils import compute_indicators
from capture_job import yield_candles

logger = logging.getLogger(__name__)

def run(symbol: str, tf: str = "M1", start: datetime = None, end: datetime = None):
    pm = PositionManager()
    for candle in yield_candles(symbol, tf, start, end):
        df = compute_indicators(pd.DataFrame([candle]))
        tech_score = 1  # placeholder
        ml_prob = predict_one(symbol, tf, df.iloc[-1])
        score = tech_score * ml_prob
        if score > 0.6:
            pm.open(symbol, candle['close'], atr=candle.get('atr', None))
        pm.update_prices(candle['close'])
    print("Equity:", pm.equity_curve)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAU_USD")
    args = parser.parse_args()
    run(args.symbol)
