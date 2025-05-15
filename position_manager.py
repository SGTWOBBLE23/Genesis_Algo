"""
Minimal position manager for back-tester & live reuse.
Breakeven + ExitNet early-exit + RR-based TP.
"""
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from datetime import datetime
from os import getenv

from ml.model_inference_rr import predict_rr
from ml.exit_inference import predict_exit_prob

logger = logging.getLogger(__name__)

API_HOST   = getenv("API_HOST", "http://127.0.0.1:8000")
ACCOUNT_ID = getenv("MT5_ACCOUNT_ID", "000000")

# ------------------------------------------------------------
#  Dataclass
# ------------------------------------------------------------
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
    # ExitNet extras
    bars_open: int = 1
    rr_hat: float = 1.5
    context_tf: str = "M15"
    ticket: int | None = None

# ------------------------------------------------------------
@dataclass
class PositionManager:
    positions: List[Position] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=lambda: [0.0])

    # --------------- OPEN ------------------------------------
    def open(
        self,
        symbol: str,
        price: float,
        atr: Optional[float] = None,
        tf: str = "M15",
        feature_dict: Optional[dict] = None,
        ticket_id: int | None = None,
    ):
        atr = atr or 0.001
        rr_hat = predict_rr(symbol, tf, feature_dict or {})
        sl = price - atr
        tp = price + rr_hat * (price - sl)

        self.positions.append(
            Position(
                symbol, "buy", price, sl, tp, 1.0, time.time(),
                rr_hat=rr_hat,
                context_tf=tf,
                ticket=ticket_id,
            )
        )

    # --------------- UPDATE BAR ------------------------------
    def update_prices(
        self,
        price: float,
        high: float,
        low: float,
        atr: float | None = None,
    ):
        eq = self.equity_curve[-1]
        for p in list(self.positions):
            # breakeven
            if not p.breakeven_moved and price - p.entry >= (p.entry - p.sl):
                p.sl = p.entry
                p.breakeven_moved = True

            # ExitNet features
            risk     = max(price - p.sl, 1e-6)
            rr_live  = (p.tp - price) / risk
            features = {
                "bars_open":   p.bars_open,
                "atr":         atr or abs(high - low),
                "range":       abs(high - low),
                "session_hour": datetime.utcnow().hour,
                "entry_rr_hat": p.rr_hat,
                "unrealised_rr": rr_live,
            }
            p_hold = predict_exit_prob(p.symbol, p.context_tf, features)
            logger.debug("ExitNet %s p_hold=%.2f", p.symbol, p_hold)

            if p_hold < 0.40:
                self._send_close_ticket(p)
                eq += max(0, price - p.entry)
                self.positions.remove(p)
                continue

            # SL / TP hit
            if price <= p.sl:
                eq -= (p.entry - p.sl)
                self.positions.remove(p)
            elif price >= p.tp:
                eq += (p.tp - p.entry)
                self.positions.remove(p)

            p.bars_open += 1

        self.equity_curve.append(eq)

    # --------------- helper ----------------------------------
    def _send_close_ticket(self, pos: Position):
        if pos.ticket is None:
            return
        try:
            requests.post(
                f"{API_HOST}/mt5/close_ticket",
                json={"account_id": ACCOUNT_ID, "ticket": int(pos.ticket)},
                timeout=2,
            )
        except Exception as exc:
            logger.error("close_ticket POST failed: %s", exc)
