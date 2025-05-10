"""
Thread‑safe model loader + predictor for live pipeline.
"""
from functools import lru_cache
import joblib
from pathlib import Path
import pandas as pd

def _model_path(tf: str = "H1") -> Path:
    return Path("models") / f"xgb_{tf}.bin"

@lru_cache(maxsize=4)
def _load(tf: str = "H1"):
    p = _model_path(tf)
    if p.exists():
        return joblib.load(p)
    return None

def predict_one(symbol: str, tf: str, feature_row) -> float:
    model = _load(tf)
    if model is None:
        return 1.0   # neutral weight if model absent
    X = pd.DataFrame([feature_row])
    X['symbol'] = symbol
    proba = model.predict_proba(X)[0][1]
    return float(proba)
