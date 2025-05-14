"""
Minimal position manager for back‑tester & potential live reuse.
Implements: open trade, move SL to breakeven at 1:1 RR.
No trailing stop (per user).
"""
from dataclasses import dataclass, field
from typing import List, Optional
from ml.model_inference_rr import predict_rr


@dataclass
class Position:
    symbol: str
    side: str        # "buy" or "sell"
    entry: float
    sl: float
    tp: float
    qty: float
    open_time: float
    breakeven_moved: bool = False

@dataclass
class PositionManager:
    positions: List[Position] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=lambda: [0.0])

    def open(
        self,
        symbol: str,
        price: float,
        atr: Optional[float] = None,
        tf: str = "M5",                 # ← tell the helper what timeframe this is
        feature_dict: Optional[dict] = None,   # ← whatever you already pass to prob model
    ):
        """Open a BUY position – TP set by model-predicted RR.

        • SL is still 1 × ATR for a simple volatility guardrail.
        • RR is predicted fresh for *this* setup, not hard-coded.
        """
        atr = atr or 0.001             # fallback if you call with atr=None
        rr_hat = predict_rr(symbol, tf, feature_dict or {})   # e.g. 1.37

        sl = price - atr               # 1 × ATR guard
        tp = price + rr_hat * (price - sl)

        self.positions.append(
            Position(symbol, "buy", price, sl, tp, 1.0, 0.0)
        )


    def update_prices(self, price: float):
        eq = self.equity_curve[-1]
        for p in list(self.positions):
            if not p.breakeven_moved and price - p.entry >= (p.entry - p.sl):
                p.sl = p.entry
                p.breakeven_moved = True
            if price <= p.sl:
                eq -= (p.entry - p.sl)
                self.positions.remove(p)
            elif price >= p.tp:
                eq += (p.tp - p.entry)
                self.positions.remove(p)
        self.equity_curve.append(eq)
