import enum
import json
from sqlalchemy.sql import func
from typing import Dict, Any, Optional, List, Union
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, DateTime, Float, String, Boolean, Integer, Enum


# This will be set when app.py creates the SQLAlchemy instance
db = SQLAlchemy()

class Role(enum.Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class TradeStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    PARTIALLY_CLOSED = "PARTIALLY_CLOSED"


class SignalStatus(enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    TRIGGERED = "TRIGGERED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SignalAction(enum.Enum):
    ANTICIPATED_LONG = "ANTICIPATED_LONG"
    ANTICIPATED_SHORT = "ANTICIPATED_SHORT"
    BUY_NOW = "BUY_NOW"
    SELL_NOW = "SELL_NOW"


class TradeSide(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class LogLevel(enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

# Model definitions will be added after db is initialized
# ---------------------------------------------------------------------------
# Signal table  (caps MT5 feed at 5, de-dups, tracks 'sent' flag)
# ---------------------------------------------------------------------------
class Signal(db.Model):
    __tablename__ = "signals"

    id         = db.Column(Integer, primary_key=True)
    symbol     = db.Column(String(15),  nullable=False)
    action     = db.Column(Enum(SignalAction), nullable=False)
    entry      = db.Column(Float,  nullable=False)
    sl         = db.Column(Float,  nullable=False)
    tp         = db.Column(Float,  nullable=False)
    tf_start   = db.Column(DateTime, nullable=False)        # candle start-time
    confidence = db.Column(Float,  nullable=True)
    created_at = db.Column(DateTime(timezone=True),
                           server_default=func.now(),
                           nullable=False)

    # NEW: tracks whether MT5 has already consumed this row
    sent       = db.Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        # NEW: hard-stop on duplicates (same idea, adjust cols if needed)
        UniqueConstraint(
            "symbol", "action", "entry", "sl", "tp", "tf_start",
            name="uix_signal_dedup"
        ),
    )

    # Handy method MT5 endpoint already expects
    def to_dict(self):
        return {
            "id":         self.id,
            "symbol":     self.symbol,
            "action":     self.action.value,
            "entry":      self.entry,
            "sl":         self.sl,
            "tp":         self.tp,
            "tf_start":   self.tf_start.isoformat(),
            "confidence": self.confidence,
        }