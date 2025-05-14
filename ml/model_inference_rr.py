#!/usr/bin/env python3
"""
GENESIS – ML inference helper

Loads a pickled sklearn/XGBoost model for a given timeframe and
returns a probability that the *positive* class (trade succeeds)
will occur.  If the model file is missing or corrupted we fall
back to a neutral DummyModel that always returns 0.50 so the
caller can continue without raising.

Public API
----------
predict_one(symbol: str, timeframe: str, features: dict) -> float
"""

from __future__ import annotations

import os
import logging
from functools import lru_cache
from typing import Dict

import joblib
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ――― Directory that holds the *.pkl models ―――
THIS_DIR = os.path.dirname(__file__)
MODELS_DIR = os.path.join(THIS_DIR, "models")          # e.g. ml/models/GBPJPY_H1.pkl

# ――― RR regression models live alongside prob models ―――
_RR_CACHE: Dict[str, Any] = {}

def _load_rr(timeframe: str, symbol: str):
    """Lazy‑load per‑symbol RR model."""
    key = f"{symbol}_{timeframe}"
    if key in _RR_CACHE:
        return _RR_CACHE[key]

    fname = f"{symbol}_{timeframe}_rr.pkl"
    fpath = os.path.join(MODELS_DIR, fname)
    if not os.path.exists(fpath):
        logger.warning("RR model %s missing – falling back to 1.5 RR", fpath)
        return None
    model = joblib.load(fpath)
    _RR_CACHE[key] = model
    return model

def predict_rr(symbol: str, timeframe: str, features: dict) -> float:
    """Return the model‑predicted optimal RR (≥1.0)."""
    model = _load_rr(timeframe, symbol)
    if model is None:
        return 1.5
    X = pd.DataFrame([features])[model.feature_names_in_]
    rr_hat = float(model.predict(X)[0])
    return max(1.0, rr_hat)


class DummyModel:
    """Fallback model used when a real model cannot be loaded."""

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:          # noqa: N802  (keep sklearn style)
        # Return 0.5 / 0.5 for every row so downstream code sees a
        # perfectly neutral probability instead of crashing.
        n = len(X)
        return np.tile([0.5, 0.5], (n, 1))


# ──────────────────────────────────────────────────────────────
#  Internal cache so each model is read from disk just once
# ──────────────────────────────────────────────────────────────
@lru_cache(maxsize=64)
def _load(timeframe: str):
    """
    Load (and cache) an ML model for the given timeframe.

    On any failure (file missing, pickle error, version mismatch…)
    we return a DummyModel instance so callers never need their
    own try/except.
    """
    fname = f"{timeframe}.pkl"          # keep original naming convention
    path = os.path.join(MODELS_DIR, fname)

    if not os.path.exists(path):
        logger.warning("ML model file not found: %s – using DummyModel", path)
        return DummyModel()

    try:
        return joblib.load(path)
    except Exception as exc:            # pylint: disable=broad-except
        logger.error("Failed to load ML model %s: %s – using DummyModel", path, exc)
        return DummyModel()


# ──────────────────────────────────────────────────────────────
#  Public helper used by signal_scoring.evaluate_technical_conditions
# ──────────────────────────────────────────────────────────────
def predict_one(symbol: str, timeframe: str, features: Dict[str, float]) -> float:
    """
    Return the probability (0 … 1) that the proposed trade succeeds.
    """
    try:
        # ── compatibility shim ───────────────────────────
        if isinstance(features, pd.Series):          # accept Series or dict
           features = features.to_dict()

        if "signal" in features and "macd_sig" not in features:
            features = features.copy()               # shallow clone
            features["macd_sig"]  = features.pop("signal")
            features["macd_hist"] = features.pop("histogram") if "histogram" in features else 0.0
            if "volume" not in features:
                features["volume"] = 0.0
        # ─────────────────────────────────────────────────

        model = _load(timeframe)
        X = pd.DataFrame([features])[model.feature_names_in_]
        proba = model.predict_proba(X)[0][1]
        return float(proba)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error(
            "predict_one failed for %s %s – %s. Returning 0.50.",
            symbol, timeframe, exc
        )
        return 0.5