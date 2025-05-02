import enum
import json
from sqlalchemy.sql import func
from typing import Dict, Any, Optional, List, Union
from flask_sqlalchemy import SQLAlchemy

# This will be set when app.py creates the SQLAlchemy instance
db = None

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