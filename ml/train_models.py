"""
Train an XGBoost model on the labeled parquet files for all symbols.
"""

from pathlib import Path
import logging
import joblib
from typing import Tuple

import pandas as pd
from xgboost import XGBClassifier        # ← fixed import

from config import ASSETS
from ml.label_maker import LAB_DIR       # FEAT_DIR no longer needed

# ──────────────────────────────────────────────────────────────
#  Globals
# ──────────────────────────────────────────────────────────────
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────
def load_dataset(tf: str) -> Tuple[pd.DataFrame, pd.Series] | Tuple[None, None]:
    """
    Concatenate all labeled parquet files for the given timeframe and
    return (features X, labels y).

    Rows with y < 0 are ignored (unlabelled).
    """
    frames: list[pd.DataFrame] = []

    for sym in ASSETS:
        fp = LAB_DIR / f"{sym}_{tf}.parquet"
        if fp.exists():
            df = pd.read_parquet(fp)
            frames.append(df[df["y"] >= 0])     # keep supervised rows

    if not frames:
        return None, None

    df_all = pd.concat(frames).reset_index(drop=True)
    y = df_all["y"].values
    X = df_all.drop(columns=["y"])
    return X, y


# ──────────────────────────────────────────────────────────────
#  Training entry-point
# ──────────────────────────────────────────────────────────────
def run(tf: str = "M1") -> None:
    """
    Train an XGBoost binary classifier for the requested timeframe (default M1)
    and save it as models/xgb_<tf>.bin
    """
    X, y = load_dataset(tf)
    if X is None:
        logger.warning("No labeled data found.")
        return

    model = XGBClassifier(
        n_estimators=400,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="binary:logistic",
        eval_metric="logloss",
    )

    model.fit(X, y)

    out_path = MODELS_DIR / f"xgb_{tf}.bin"
    joblib.dump(model, out_path)
    logger.info("Saved model to %s", out_path)


# ──────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train XGB model")
    parser.add_argument("--tf", default="M1", help="Timeframe (e.g. M1, H1)")

    args = parser.parse_args()
    run(args.tf)
