"""
Minimal position manager for back‑tester & potential live reuse.
Implements: open trade, move SL to breakeven at 1:1 RR.
No trailing stop (per user).
"""
from dataclasses import dataclass, field
from typing import List, Optional
from ml.model_inference_rr import predict_rr,
from ml.exit_inference import predict_exit_prob
from datetime import datetime


@dataclass
class Position:
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float
    qty: float
    open_time: float
    breakeven_moved: bool = False

    # New fields for ExitNet
    bars_open: int = 1
    rr_hat: float = 1.5  # default fallback if model wasn't used

@dataclass
class PositionManager:
    positions: List[Position] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=lambda: [0.0])

    def open(
        self,
        symbol: str,
        price: float,
        atr: Optional[float] = None,
        tf: str = "M5",                 # timeframe you’re trading
        feature_dict: Optional[dict] = None
    ):
        """
        Open a *BUY* position.
        • SL = 1 × ATR guardrail
        • TP = model-predicted RR × risk
        """
        atr = atr or 0.001                            # safety fallback
        rr_hat = predict_rr(symbol, tf, feature_dict or {})  # e.g. 1.37

        sl = price - atr                              # BUY only
        tp = price + rr_hat * (price - sl)            # risk = price-sl
        breakeven_trigger = 0.5 * rr_hat              # used elsewhere

        self.positions.append(
            Position(symbol, "buy", price, sl, tp, 1.0, time.time(), rr_hat=rr_hat)
        )


    def update_prices(self, price: float):
        eq = self.equity_curve[-1]
        for p in list(self.positions):
            # Breakeven logic (unchanged)
            if not p.breakeven_moved and price - p.entry >= (p.entry - p.sl):
                p.sl = p.entry
                p.breakeven_moved = True

            # Calculate unrealised RR
            rr_live = (p.tp - price) / (price - p.sl)

            # Build features for ExitNet
            features = {
                "bars_open": getattr(p, "bars_open", 1),
                "atr": abs(p.tp - p.sl),  # use static ATR from entry for now
                "range": abs(price - p.entry),  # proxy for current bar range
                "session_hour": datetime.utcnow().hour,
                "entry_rr_hat": getattr(p, "rr_hat", 1.5),
                "unrealised_rr": rr_live
            }
            
            p_hold = predict_exit_prob(p.symbol, "M15", features)  # change to "H1" if needed
            print(f"[ExitNet] {p.symbol} p_hold={p_hold:.2f} rr={p.rr_hat:.2f} bars={p.bars_open}")

            # ExitNet decision: close early if losing edge
            if p_hold < 0.40:
                eq += max(0, price - p.entry)  # add any open gain
                self.positions.remove(p)
                continue
                print(f"🔴 ExitNet: Closing {p.symbol} early at price {price:.2f} | p_hold={p_hold:.2f}")


            # SL / TP logic
            if price <= p.sl:
                eq -= (p.entry - p.sl)
                self.positions.remove(p)
            elif price >= p.tp:
                eq += (p.tp - p.entry)
                self.positions.remove(p)

            # Track how long trade has been open
            p.bars_open = getattr(p, "bars_open", 1) + 1

        self.equity_curve.append(eq)
