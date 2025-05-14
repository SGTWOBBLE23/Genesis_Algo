
"""
exit_inference.py – Load ExitNet and return p_hold for open trades
"""

import os
import joblib
import logging
import pandas as pd
from typing import Dict

logger = logging.getLogger(__name__)
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
_EXIT_CACHE = {}

def _load_exit(symbol: str, tf: str):
    key = f"{symbol}_{tf}_exit"
    if key in _EXIT_CACHE:
        return _EXIT_CACHE[key]

    fname = f"{symbol}_{tf}_exit.pkl"
    fpath = os.path.join(MODELS_DIR, fname)
    if not os.path.exists(fpath):
        logger.warning("Missing ExitNet model: %s", fpath)
        return None
    model = joblib.load(fpath)
    _EXIT_CACHE[key] = model
    return model

def predict_exit_prob(symbol: str, tf: str, features: Dict) -> float:
    """
    Return probability the trade is still good (should HOLD)
    """
    model = _load_exit(symbol, tf)
    if not model:
        return 0.5  # fallback: uncertain
    df = pd.DataFrame([features])[model.feature_names_in_]
    return float(model.predict_proba(df)[0][1])  # class 1 = hold
