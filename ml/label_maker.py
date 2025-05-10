"""
Create supervised labels by joining Trade outcomes onto candle features.
Assumes Trade model has columns: symbol, opened_at, closed_at, pnl.
"""
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from app import db, Trade
from config import ASSETS

FEAT_DIR = Path("data/features")
LAB_DIR = Path("data/labeled")
LAB_DIR.mkdir(parents=True, exist_ok=True)

def label(symbol: str, tf: str = "M1"):
    feat_path = FEAT_DIR / f"{symbol}_{tf}.parquet"
    if not feat_path.exists():
        return
    df = pd.read_parquet(feat_path)
    session: Session = db.session
    trades = session.query(Trade).filter(Trade.symbol == symbol).all()
    label_series = pd.Series(index=df.index, data=-1, dtype="int8")
    for tr in trades:
        # find index of entry candle nearest <= opened_at
        mask = (df['time'] <= tr.opened_at).values
        if not mask.any():
            continue
        idx = mask.nonzero()[0][-1]
        label_series.iloc[idx] = int(tr.pnl > 0)
    df['y'] = label_series
    out_path = LAB_DIR / f"{symbol}_{tf}.parquet"
    df.to_parquet(out_path)
