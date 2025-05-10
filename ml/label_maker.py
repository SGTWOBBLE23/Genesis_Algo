"""
Create supervised labels by joining Trade outcomes onto candle features.

If a Trade table is available (via app.db) we mark the entry-candle
with y = 1 (win) or 0 (loss).  Rows with no label keep y = -1.

When no Trade table or rows exist we fall back to a simple
“next-candle direction” heuristic:

    y = 1  if close_(t+1) > close_t
    y = 0  if close_(t+1) <= close_t

That lets you train higher-timeframe models (e.g. H1) even before you
have live trade data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd
from config import ASSETS

FEAT_DIR = Path("data/features")
LAB_DIR  = Path("data/labels")          # keep in sync with train_models.py
LAB_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────
def _labels_from_trades(df: pd.DataFrame, trades: List) -> pd.Series:
    """
    Return a Series aligned to df.index with y = 1/0 where we can match
    trade entry-times, and -1 elsewhere.
    """
    label_series = pd.Series(index=df.index, data=-1, dtype="int8")

    for tr in trades:
        # entry candle nearest <= opened_at
        mask = (df["time"] <= tr.opened_at).values
        if not mask.any():
            continue
        idx = mask.nonzero()[0][-1]
        label_series.iloc[idx] = int(tr.pnl > 0)

    return label_series


def _labels_from_price_action(df: pd.DataFrame) -> pd.Series:
    """
    Heuristic fallback when no trades are available:
    label = 1 if next candle closes higher than current, else 0.
    """
    next_close = df["close"].shift(-1)
    label_series = (next_close > df["close"]).astype("int8")
    label_series.iloc[-1] = -1      # last row has no 'next' candle
    return label_series


def label_one(symbol: str, tf: str) -> None:
    feat_path = FEAT_DIR / f"{symbol}_{tf}.parquet"
    if not feat_path.exists():
        logger.warning("Feature file missing: %s", feat_path)
        return

    df = pd.read_parquet(feat_path)

    # ----------------------------------------------------------
    #  Try to pull trade outcomes
    # ----------------------------------------------------------
    trades = []
    try:
        from app import db, Trade

        session = db.session
        trades = (
            session.query(Trade)
            .filter(Trade.symbol == symbol)
            .all()
        )
        logger.info("Fetched %d trades for %s", len(trades), symbol)
    except Exception as exc:
        logger.info("No Trade table available (%s) – using price-action labels", exc)

    if trades:
        df["y"] = _labels_from_trades(df, trades)
    else:
        df["y"] = _labels_from_price_action(df)

    out_path = LAB_DIR / f"{symbol}_{tf}.parquet"
    df.to_parquet(out_path)
    logger.info("Wrote labels: %s  (rows=%d)", out_path, len(df))


def run(tf: str = "M1") -> None:
    """
    Generate label parquet for every symbol in ASSETS at timeframe *tf*.
    """
    logger.info("Building labels for TF=%s …", tf)
    for sym in ASSETS:
        label_one(sym, tf)
    logger.info("Finished label build for TF=%s", tf)


# ──────────────────────────────────────────────────────────────
#  CLI entry-point
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build label parquet files")
    parser.add_argument(
        "--tf",
        default="M1",
        help="Time-frame (M1, H1, etc.) matching feature parquet names",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    run(args.tf)
