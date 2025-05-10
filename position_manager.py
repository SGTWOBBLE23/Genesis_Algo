"""
Minimal position manager for back‑tester & potential live reuse.
Implements: open trade, move SL to breakeven at 1:1 RR.
No trailing stop (per user).
"""
from dataclasses import dataclass, field
from typing import List, Optional

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

    def open(self, symbol: str, price: float, atr: Optional[float] = None, rr: float = 1.0):
        sl = price - atr if atr else price - 0.001
        tp = price + (price - sl) * rr
        self.positions.append(Position(symbol, "buy", price, sl, tp, 1.0, 0.0))

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
