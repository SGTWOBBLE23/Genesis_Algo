#!/usr/bin/env python3
"""
Back-fill OANDA candles **and** write fully-labelled feature sets.

• Builds numeric features via ml.feature_builder.build_features
• Adds binary label `y` (future +0.1 % in the next bar → 1 ; else 0)
• Saves one Parquet per symbol to data/labels/<SYMBOL>_<TF>.parquet
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from capture_job import yield_candles          # ← your existing helper
from config import ASSETS
from ml.feature_builder import build_features

# ──────────────────────────────────────────────────────────────
#  Constants & paths
# ──────────────────────────────────────────────────────────────
LABEL_DIR = Path("data") / "labels"
LABEL_DIR.mkdir(parents=True, exist_ok=True)

THRESH_PCT  = 0.001      # 0.1 %
LABEL_SHIFT = 1          # look-ahead bars

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────
def add_label(df: pd.DataFrame) -> pd.DataFrame:
    """Append binary `y` column based on a simple future-price threshold."""
    next_close = df["close"].shift(-LABEL_SHIFT)
    df["y"] = (next_close >= df["close"] * (1 + THRESH_PCT)).astype("int8")
    df.loc[df.index[-LABEL_SHIFT:], "y"] = -1        # mark last row(s)
    return df


def build_and_save(symbol: str, tf: str, years: int) -> None:
    """Fetch candles → build features → add label → write Parquet."""
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years)

    rows = [c for c in yield_candles(symbol, tf, start, end)]   # ← fixed
    if not rows:
        log.warning("No data for %s", symbol)
        return

    df_raw  = pd.DataFrame(rows)
    df_feat = build_features(df_raw)
    df_lbl  = add_label(df_feat)

    out_fp = LABEL_DIR / f"{symbol}_{tf}.parquet"
    df_lbl.to_parquet(out_fp, index=False)
    log.info("Wrote %d labelled rows to %s", len(df_lbl), out_fp)


# ──────────────────────────────────────────────────────────────
#  Main runner
# ──────────────────────────────────────────────────────────────
def run(years: int = 2, tf: str = "H1") -> None:
    tf = tf.upper()
    for sym in ASSETS:
        try:
            build_and_save(sym, tf, years)
        except Exception as exc:                      # pylint: disable=broad-except
            log.exception("Failed %s %s – %s", sym, tf, exc)


# ──────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=2, help="Years of history")
    p.add_argument("--tf",    type=str, default="H1", help="Time-frame (M1/M15/H1)")
    args = p.parse_args()
    run(args.years, args.tf)
