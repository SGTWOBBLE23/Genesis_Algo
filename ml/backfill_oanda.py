#!/usr/bin/env python3
"""
Download historical candles from OANDA using the *same* client your live code uses.
The script pages backwards 5 000 candles at a time until the requested `--years`
limit is hit.  Output is one parquet per year under `data/raw/<SYMBOL>/<TF>/`.
Run once, then incremental capture job will keep data fresh.
"""

import argparse, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

from oanda_api import OandaAPI
from capture_job import yield_candles
from config import ASSETS

logger = logging.getLogger(__name__)
DATA_DIR = Path("data") / "raw"

def run(years: int = 15, tf: str = "M1"):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365*years)
    api = OandaAPI()
    for sym in ASSETS:
        out_dir = DATA_DIR / sym / tf
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for candle in yield_candles(sym, tf, start, end):
            rows.append(candle)
        if not rows:
            logger.warning("No data for %s", sym)
            continue
        df = pd.DataFrame(rows)
        df.to_parquet(out_dir / f"{start.year}_{end.year}.parquet")
        logger.info("Wrote %d candles for %s", len(df), sym)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=15)
    parser.add_argument("--tf", type=str, default="M1")
    args = parser.parse_args()
    run(args.years, args.tf)
