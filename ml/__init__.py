"""Intraday ML package.  Loaded lazily by live pipeline."""

from pathlib import Path
import joblib

_MODEL_CACHE = {}

def _model_path(tf: str = "H1") -> Path:
    root = Path(__file__).parent.parent / "models"
    return root / f"xgb_{tf}.bin"

def load_model(tf: str = "H1"):
    if tf not in _MODEL_CACHE:
        p = _model_path(tf)
        if p.exists():
            _MODEL_CACHE[tf] = joblib.load(p)
        else:
            _MODEL_CACHE[tf] = None
    return _MODEL_CACHE[tf]
