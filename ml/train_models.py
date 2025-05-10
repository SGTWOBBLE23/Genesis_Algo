#!/usr/bin/env python3
"""
Resource-lean XGBoost trainer.

• Uses the last 100 k rows per symbol (≈ 4 months of M1 data)
• Limits XGBoost to 4 threads to avoid Replit watchdog kills
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

import pandas as pd
from xgboost import XGBClassifier
from joblib import dump                  # ←───────────── NEW

from config import ASSETS

# ──────────────────────────────────────────────────────────────
#  Paths & logging
# ──────────────────────────────────────────────────────────────
LAB_DIR     = Path("data/labels")
MODELS_DIR  = Path("ml/models")          # ←───────────── CHANGED  (was "models")
LAB_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────
MAX_KEEP = 100_000            # last N rows per symbol
THREADS  = 4                  # limit OMP threads

os.environ["OMP_NUM_THREADS"] = str(THREADS)


def load_dataset(tf: str) -> tuple[pd.DataFrame, pd.Series] | tuple[None, None]:
    frames: List[pd.DataFrame] = []

    for sym in ASSETS:
        fp = LAB_DIR / f"{sym}_{tf}.parquet"
        if not fp.exists():
            continue

        df = pd.read_parquet(fp)
        df = df[df["y"] >= 0]          # keep supervised rows
        if len(df) > MAX_KEEP:
            df = df.iloc[-MAX_KEEP:]   # keep most-recent slice
        frames.append(df)

    if not frames:
        return None, None

    df_all = pd.concat(frames).reset_index(drop=True)
    y = df_all["y"].astype("int8").values
    X = df_all.drop(columns=["y"]).select_dtypes(include=["number", "bool"])
    return X, y


# ──────────────────────────────────────────────────────────────
#  Train
# ──────────────────────────────────────────────────────────────
def run(tf: str = "M1") -> None:
    X, y = load_dataset(tf)
    if X is None:
        logger.warning("No labelled data found for %s", tf)
        return

    logger.info("Training on %s rows × %s features", len(X), X.shape[1])

    model = XGBClassifier(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        tree_method="hist",
        nthread=THREADS,
        eval_metric="logloss",
        objective="binary:logistic",
    )
    model.fit(X, y)

    # ─────────────── SAVE BOTH FORMATS ───────────────
    # 1) Native XGBoost binary (optional – keep if you want)
    bin_path = MODELS_DIR / f"xgb_{tf}.bin"
    model.save_model(bin_path)
    logger.info("Saved XGB binary to %s", bin_path)

    # 2) Joblib pickle that model_inference expects
    pkl_path = MODELS_DIR / f"{tf}.pkl"          # "H1.pkl", "M1.pkl", etc.
    dump(model, pkl_path)
    logger.info("Saved joblib model to %s", pkl_path)


# ──────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="RAM-safe XGBoost trainer")
    p.add_argument("--tf", default="M1", help="Timeframe (M1, H1, etc.)")
    args = p.parse_args()
    run(args.tf)
