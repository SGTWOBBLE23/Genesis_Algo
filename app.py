import os
import logging
import enum
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union

from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func
from sqlalchemy import and_

# Configure logging with custom filter for important INFO logs
class ImportantInfoFilter(logging.Filter):
    """Filter that allows only important INFO logs through"""
    def filter(self, record):
        # Always allow WARNING, ERROR, CRITICAL, etc.
        if record.levelno >= logging.WARNING:
            return True

        # Keep these important INFO logs
        important_patterns = [
            "signal", "trade", "update", "created", "sent", "received", 
            "market data", "connected", "connection", "starting", "completed", 
            "success", "error", "warning", "fatal", "critical",
            "executed", "processed", "filtered", "analyzing", "completed", "generated"
        ]

        # Filter out these verbose INFO logs
        excessive_patterns = [
            "Using original closed_at time", 
            "Found null character in the request data", 
            "Successfully parsed cleaned JSON",
            "heartbeat",
            "Account status update",
            "Account status updated",
            "Processed signal IDs"
        ]

        # Special case for mt5_ea_api - only keep certain important logs
        if record.name == 'mt5_ea_api' and record.levelno == logging.INFO:
            # Always filter out these specific message patterns
            if "Using original closed_at time from MT5" in record.getMessage():
                return False
            if "Processed signal IDs:" in record.getMessage():
                return False
            if "Account status update" in record.getMessage():
                return False
            if "Found null character" in record.getMessage():
                return False
            if "Successfully parsed cleaned JSON" in record.getMessage():
                return False

            # Filter out other excessive logs
            for pattern in excessive_patterns:
                if pattern in record.getMessage():
                    return False

            # Check if message contains an important pattern
            for pattern in important_patterns:
                if pattern in record.getMessage().lower():
                    return True

            # For mt5_ea_api, default to filtering out INFO unless explicitly allowed
            return False

        # For all other loggers, keep INFO logs by default
        return True

# Configure main logging
logging.basicConfig(
    level=logging.INFO,  # Changed from DEBUG to INFO
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Apply custom filter to root logger
root_logger = logging.getLogger()
root_logger.addFilter(ImportantInfoFilter())

# Set higher log level for specific loggers with excessive output
mt5_logger = logging.getLogger('mt5_ea_api')

# Create a handler that ensures important MT5 logs are still captured
mt5_handler = logging.StreamHandler()
mt5_handler.setLevel(logging.INFO)

# Define custom filter for MT5 logs that only allows important INFO messages
class MT5ImportantFilter(logging.Filter):
    def filter(self, record):
        # Always allow WARNING and above
        if record.levelno >= logging.WARNING:
            return True

        # Filter for important MT5 activities
        important_mt5_patterns = [
            "signal", "trade", "execution", "force_execution", 
            "request from MT5", "response to MT5", "ticket",
            "opened", "closed", "triggered"
        ]

        # Check if message contains any important patterns
        for pattern in important_mt5_patterns:
            if pattern in record.getMessage().lower():
                return True

        # Otherwise, filter it out
        return False

# Add filter and handler to MT5 logger
mt5_handler.addFilter(MT5ImportantFilter())
mt5_logger.addHandler(mt5_handler)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "genesis_trading_platform_secret")

# Configure the SQLAlchemy database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize SQLAlchemy
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)

# ---- Enum Definitions ----
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
    ERROR = "ERROR"

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

# ---- Model Definitions ----
class User(db.Model):
    """User model for authentication"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    hashed_pw = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), default=Role.USER)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Settings(db.Model):
    """Settings key-value store with sections"""
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(50), nullable=False)
    key = db.Column(db.String(100), nullable=False)
    value_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    __table_args__ = (db.UniqueConstraint('section', 'key', name='uix_section_key'),)

    @property
    def value(self) -> Any:
        if self.value_json is None:
            return None
        return json.loads(self.value_json)

    @value.setter
    def value(self, val: Any) -> None:
        self.value_json = json.dumps(val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "section": self.section,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def get_value(cls, section: str, key: str, default: Any = None) -> Any:
        """Get a setting value by section and key"""
        setting = cls.query.filter_by(section=section, key=key).first()
        if setting is None:
            return default
        return setting.value

    @classmethod
    def set_value(cls, section: str, key: str, value: Any) -> None:
        """Set a setting value by section and key"""
        setting = cls.query.filter_by(section=section, key=key).first()
        if setting is None:
            setting = cls(section=section, key=key)
            db.session.add(setting)
        setting.value = value
        db.session.commit()

    @classmethod
    def get_section(cls, section: str) -> Dict[str, Any]:
        """Get all settings in a section"""
        settings = cls.query.filter_by(section=section).all()
        return {s.key: s.value for s in settings}

class Signal(db.Model):
    """Trading signals from Vision analysis"""
    __tablename__ = "signals"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False)
    action = db.Column(db.Enum(SignalAction), nullable=False)
    entry = db.Column(db.Float, nullable=True)
    sl = db.Column(db.Float, nullable=True)
    tp = db.Column(db.Float, nullable=True)
    confidence = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum(SignalStatus), default=SignalStatus.PENDING)
    context_json = db.Column(db.Text, nullable=True)  # Additional signal context
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    trades = db.relationship("Trade", back_populates="signal")

    @property
    def context(self) -> Dict[str, Any]:
        if self.context_json is None:
            return {}
        return json.loads(self.context_json)

    @context.setter
    def context(self, val: Dict[str, Any]) -> None:
        self.context_json = json.dumps(val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "action": self.action.value,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "confidence": self.confidence,
            "status": self.status.value,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Trade(db.Model):
    """Executed trades from signals or manual entry"""
    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True)
    signal_id = db.Column(db.Integer, db.ForeignKey("signals.id"), nullable=True)
    ticket = db.Column(db.String(50), nullable=True)  # MT5 ticket number
    symbol = db.Column(db.String(20), nullable=False)
    side = db.Column(db.Enum(TradeSide), nullable=False)
    lot = db.Column(db.Float, nullable=False)
    entry = db.Column(db.Float, nullable=True)
    exit = db.Column(db.Float, nullable=True)
    sl = db.Column(db.Float, nullable=True)
    tp = db.Column(db.Float, nullable=True)
    pnl = db.Column(db.Float, nullable=True)
    status = db.Column(db.Enum(TradeStatus), default=TradeStatus.OPEN)
    opened_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    context = db.Column(db.Text, nullable=True)  # Additional trade context
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    signal = db.relationship("Signal", back_populates="trades")

    @property
    def context(self) -> Dict[str, Any]:
        if self.context_json is None:
            return {}
        return json.loads(self.context_json)

    @context.setter
    def context(self, val: Dict[str, Any]) -> None:
        self.context_json = json.dumps(val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "signal_id": self.signal_id,
            "ticket": self.ticket,
            "symbol": self.symbol,
            "side": self.side.value,
            "lot": self.lot,
            "entry": self.entry,
            "exit": self.exit,
            "sl": self.sl,
            "tp": self.tp,
            "pnl": self.pnl,
            "status": self.status.value,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Log(db.Model):
    """System logs"""
    __tablename__ = "logs"

    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, server_default=func.now())
    level = db.Column(db.Enum(LogLevel), nullable=False)
    source = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    context_json = db.Column(db.Text, nullable=True)

    @property
    def context(self) -> Optional[Dict[str, Any]]:
        if self.context_json is None:
            return None
        return json.loads(self.context_json)

    @context.setter
    def context(self, val: Optional[Dict[str, Any]]) -> None:
        if val is None:
            self.context_json = None
        else:
            self.context_json = json.dumps(val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ts": self.ts.isoformat() if self.ts else None,
            "level": self.level.value,
            "source": self.source,
            "message": self.message,
            "context": self.context,
        }

    @classmethod
    def add(cls, level: Union[LogLevel, str], source: str, message: str, context: Optional[Dict[str, Any]] = None) -> "Log":
        """Add a new log entry"""
        if isinstance(level, str):
            level = LogLevel(level.upper())
        log = cls(level=level, source=source, message=message, context=context)
        db.session.add(log)
        db.session.commit()
        return log

# Risk Profile class for storing risk management profiles
class RiskProfile(db.Model):
    """Risk management profiles"""
    __tablename__ = "risk_profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    json_rules = db.Column(db.Text, nullable=False)  # JSON string of risk rules
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now())

    @property
    def rules(self) -> Dict[str, Any]:
        return json.loads(self.json_rules)

    @rules.setter
    def rules(self, val: Dict[str, Any]) -> None:
        self.json_rules = json.dumps(val)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "is_default": self.is_default,
            "rules": self.rules,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

# ---- Service Classes ----
class MT5Service:
    """Service for MetaTrader 5 integration"""

    def __init__(self):
        self.endpoint = None
        self.token = None
        logger.info("MT5 service initialized")

    def update_endpoint(self, endpoint, token=None):
        self.endpoint = endpoint
        if token:
            self.token = token

    def test_connection(self):
        # Simulated test for now
        return True if self.endpoint else False

    def open_trade(self, trade_data):
        # Simulated trade execution
        if not self.endpoint:
            return None
        return {"ticket": "12345", "status": "OPENED"}

class OandaService:
    """Service for OANDA integration"""

    def __init__(self):
        self.api_key = os.environ.get("OANDA_API_KEY")
        self.account_id = os.environ.get("OANDA_ACCOUNT_ID")
        self.api = None
        if self.api_key and self.account_id:
            self._init_api()
        logger.info("OANDA service initialized")

    def _init_api(self):
        from oanda_api import OandaAPI
        self.api = OandaAPI(self.api_key, self.account_id)

    def update_api_key(self, api_key, account_id):
        self.api_key = api_key
        self.account_id = account_id
        if self.api_key and self.account_id:
            self._init_api()

    def test_connection(self):
        if not self.api:
            return False
        return self.api.test_connection()

    def account_info(self):
        if not self.api:
            return None
        result = self.api.get_account_summary()
        if "error" in result:
            logger.error(f"Error getting account info: {result['error']}")
            return None
        return result

    def get_instruments(self):
        if not self.api:
            return []
        return self.api.get_instruments()

    def get_candles(self, instrument, granularity="H1", count=50):
        if not self.api:
            return []
        return self.api.get_candles(instrument, granularity, count)

    def get_open_trades(self):
        if not self.api:
            return []
        return self.api.get_open_trades()

class VisionService:
    """Service for OpenAI Vision API integration"""

    def __init__(self):
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.model = "gpt-4o"
        logger.info("Vision service initialized with API key")

    def update_api_key(self, api_key, model=None):
        self.api_key = api_key
        if model:
            self.model = model

    def analyze_chart(self, image_data):
        # Simulated analysis for now
        return {
            "action": "BUY_NOW",
            "confidence": 0.85,
            "entry": 1.0750,
            "sl": 1.0720,
            "tp": 1.0800
        }

class RiskService:
    """Service for risk management"""

    def __init__(self):
        try:
            # Try to load default risk profile from database
            default_profile = db.session.query(RiskProfile).filter_by(is_default=True).first()
            if default_profile:
                self.default_rules = default_profile.json_rules
            else:
                logger.warning("Database not available for risk profile query")
                self.default_rules = self._get_default_rules()
        except Exception:
            logger.warning("Database not available for risk profile query")
            self.default_rules = self._get_default_rules()

        logger.info("Risk service initialized with default profile")

    def _get_default_rules(self):
        return {
            "max_lot_size": 1.0,
            "max_daily_loss": 2.0,  # Percentage of account
            "max_position_risk": 1.0,  # Percentage of account per position
            "auto_sl": True,
            "default_sl_pips": 30
        }

    def calculate_position_size(self, account_balance, risk_percent, entry, stop_loss):
        # Basic position sizing calculation
        if entry == stop_loss:
            return 0.0

        pip_risk = abs(entry - stop_loss) * 10000  # Assuming 4 decimal places
        dollar_risk = account_balance * (risk_percent / 100)
        lot_size = dollar_risk / pip_risk

        # Apply max lot size limit
        max_lot = self.default_rules.get("max_lot_size", 1.0)
        return min(lot_size, max_lot)

class TelegramService:
    """Service for Telegram notifications"""

    def __init__(self):
        self.bot_token = None
        self.chat_id = None
        logger.info("Telegram service initialized")

    def update_token(self, token, chat_id=None):
        self.bot_token = token
        if chat_id:
            self.chat_id = chat_id

    def send_message(self, message):
        # Simulated message sending
        if not self.bot_token or not self.chat_id:
            return False
        logger.info(f"Telegram message would be sent: {message}")
        return True

    def send_trade_alert(self, trade_data):
        # Format and send trade alert
        message = f"🚨 NEW TRADE: {trade_data['symbol']} {trade_data['side']}\n"
        message += f"Lot: {trade_data['lot']}\n"
        message += f"Entry: {trade_data['entry']}\n"
        if trade_data['sl']:
            message += f"SL: {trade_data['sl']}\n"
        if trade_data['tp']:
            message += f"TP: {trade_data['tp']}\n"
        return self.send_message(message)

# Initialize services
mt5_service = MT5Service()
oanda_service = OandaService()
vision_service = VisionService()
risk_service = RiskService()
telegram_service = TelegramService()

# ---- Routes ----
@app.route('/')
def index():
    # Get MT5 account info to display on dashboard
    mt5_account = {
        'balance': Settings.get_value('mt5_account', 'balance', 0.0),
        'equity': Settings.get_value('mt5_account', 'equity', 0.0),
        'margin': Settings.get_value('mt5_account', 'margin', 0.0),
        'free_margin': Settings.get_value('mt5_account', 'free_margin', 0.0),
        'leverage': Settings.get_value('mt5_account', 'leverage', 1),
        'open_positions': Settings.get_value('mt5_account', 'open_positions', 0),
        'account_id': Settings.get_value('mt5_account', 'id', 'Not connected'),
        'last_update': Settings.get_value('mt5_account', 'last_update', None)
    }

    # Check if there's an active MT5 connection
    last_heartbeat = Settings.get_value('mt5', 'last_heartbeat', None)
    mt5_connected = False
    if last_heartbeat:
        try:
            # Parse the timestamp and check if it's recent (within the last 5 minutes)
            last_time = datetime.fromisoformat(last_heartbeat)
            mt5_connected = (datetime.now() - last_time).total_seconds() < 300
        except:
            mt5_connected = False

    # Add connected status to the account data for the template
    mt5_account['connected'] = mt5_connected

    return render_template('index.html', title='Dashboard', mt5_account=mt5_account, mt5_connected=mt5_connected)

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/history')
def history():
    # Get MT5 account info to display on history page
    mt5_account = {
        'balance': Settings.get_value('mt5_account', 'balance', 0.0),
        'equity': Settings.get_value('mt5_account', 'equity', 0.0),
        'margin': Settings.get_value('mt5_account', 'margin', 0.0),
        'free_margin': Settings.get_value('mt5_account', 'free_margin', 0.0),
        'leverage': Settings.get_value('mt5_account', 'leverage', 1),  # Added leverage
        'open_positions': Settings.get_value('mt5_account', 'open_positions', 0),  # Added open positions
        'account_id': Settings.get_value('mt5_account', 'id', 'Not connected'),
        'last_update': Settings.get_value('mt5_account', 'last_update', None)
    }

    # Check if there's an active MT5 connection
    last_heartbeat = Settings.get_value('mt5', 'last_heartbeat', None)
    mt5_connected = False
    if last_heartbeat:
        try:
            # Parse the timestamp and check if it's recent (within the last 5 minutes)
            last_time = datetime.fromisoformat(last_heartbeat)
            mt5_connected = (datetime.now() - last_time).total_seconds() < 300
        except:
            mt5_connected = False

    # Add connected status to the account data for the template
    mt5_account['connected'] = mt5_connected

    return render_template('history.html', title='Trading History', mt5_account=mt5_account, mt5_connected=mt5_connected)

@app.route('/settings')
def settings():
    return render_template('settings.html', title='Settings')

@app.route('/downloads')
def downloads():
    return render_template('downloads.html', title='Downloads')

@app.route('/downloads/MT5_GENESIS_EA_fixed_v10.mq5')
def download_mt5_ea():
    try:
        return send_file('MT5_GENESIS_EA_fixed_v10.mq5', as_attachment=True)
    except Exception as e:
        return str(e), 404

@app.route('/downloads/MT5_GENESIS_EA_INSTRUCTIONS.md')
def download_mt5_instructions():
    try:
        return send_file('MT5_GENESIS_EA_INSTRUCTIONS.md', as_attachment=True)
    except Exception as e:
        return str(e), 404

# API Routes
@app.route('/api/trades', methods=['GET'])
def get_trades():
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        status = request.args.get('status')
        symbol = request.args.get('symbol')
        side = request.args.get('side')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Define the columns we want to select (avoiding any that might not exist in the DB)
        columns = [
            Trade.id,
            Trade.signal_id,
            Trade.ticket,
            Trade.symbol, 
            Trade.side,
            Trade.lot,
            Trade.entry,
            Trade.exit,
            Trade.sl,
            Trade.tp,
            Trade.pnl,
            Trade.status,
            Trade.opened_at,
            Trade.closed_at,
            Trade.created_at,
            Trade.updated_at
        ]

        query = db.session.query(*columns)

        # Apply filters if provided
        if status:
            try:
                query = query.filter(Trade.status == TradeStatus(status))
            except ValueError:
                # If invalid status, just ignore this filter
                pass
        if symbol:
            query = query.filter(Trade.symbol == symbol)
        if side:
            try:
                query = query.filter(Trade.side == TradeSide(side))
            except ValueError:
                # If invalid side, just ignore this filter
                pass

        # Apply date filters if provided
        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date)
                query = query.filter(Trade.opened_at >= start_date_obj)
            except (ValueError, TypeError):
                # Invalid date format, ignore
                pass

        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date)
                query = query.filter(Trade.opened_at <= end_date_obj)
            except (ValueError, TypeError):
                # Invalid date format, ignore
                pass

        # Get total count for pagination
        total_query = db.session.query(func.count(Trade.id))
        if status:
            try:
                total_query = total_query.filter(Trade.status == TradeStatus(status))
            except ValueError:
                pass
        if symbol:
            total_query = total_query.filter(Trade.symbol == symbol)
        if side:
            try:
                total_query = total_query.filter(Trade.side == TradeSide(side))
            except ValueError:
                pass

        total = total_query.scalar() or 0
        pages = (total + limit - 1) // limit if limit > 0 else 1

        # Apply pagination
        trades = query.order_by(Trade.created_at.desc()).limit(limit).offset((page - 1) * limit).all()

        # Convert to dictionaries - manually create the dict since the to_dict method might use columns not in our select
        trade_list = []
        for trade in trades:
            trade_dict = {
                "id": trade.id,
                "signal_id": trade.signal_id,
                "ticket": trade.ticket,
                "symbol": trade.symbol,
                "side": trade.side.value if trade.side else None,
                "lot": trade.lot,
                "entry": trade.entry,
                "exit": trade.exit,
                "sl": trade.sl,
                "tp": trade.tp,
                "pnl": trade.pnl,
                "status": trade.status.value if trade.status else None,
                "opened_at": trade.opened_at.isoformat() if trade.opened_at else None,
                "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
                "created_at": trade.created_at.isoformat() if trade.created_at else None,
                "updated_at": trade.updated_at.isoformat() if trade.updated_at else None,
                "context": {}
            }
            trade_list.append(trade_dict)

        return jsonify({
            'data': trade_list,
            'page': page,
            'limit': limit,
            'total': total,
            'pages': pages
        })
    except Exception as e:
        # Log error and return empty response
        print(f"Error fetching trades: {str(e)}")
        return jsonify({
            'data': [],
            'page': 1,
            'limit': 50,
            'total': 0,
            'pages': 0,
            'error': str(e)
        }), 500

@app.route('/api/trades/stats', methods=['GET'])
def get_trades_stats():
    """Get trading statistics for closed trades"""
    try:
        # Optional query parameters
        symbol = request.args.get('symbol')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Get all closed trades
        trades = db.session.query(Trade).filter(Trade.status == TradeStatus.CLOSED).all()

        # Additional filtering
        if symbol:
            trades = [t for t in trades if t.symbol == symbol]

        if start_date:
            try:
                start_date_obj = datetime.fromisoformat(start_date)
                trades = [t for t in trades if t.closed_at and t.closed_at >= start_date_obj]
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore

        if end_date:
            try:
                end_date_obj = datetime.fromisoformat(end_date)
                trades = [t for t in trades if t.closed_at and t.closed_at <= end_date_obj]
            except (ValueError, TypeError):
                pass  # Invalid date format, ignore

        # Filter out duplicates by id, not relying on ticket
        seen_ids = set()
        filtered_trades = []

        for trade in trades:
            if trade.id in seen_ids:
                continue

            seen_ids.add(trade.id)
            filtered_trades.append(trade)            

        # Initial statistics
        stats = {
            'total_trades': len(filtered_trades),
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'total_profit': 0.0,
            'max_drawdown': 0.0
        }

        # Exit early if no trades
        if not filtered_trades:
            return jsonify(stats)

        # Calculate win/loss and profit
        total_profit = 0.0
        winning_trades = []
        losing_trades = []

        for trade in filtered_trades:
            # Safely access PnL, skipping trades with no profit/loss data
            try:
                if trade.pnl is None:
                    logger.warning(f"Trade ID {trade.id} has no PnL value")
                    continue

                pnl = float(trade.pnl)
                total_profit += pnl

                if pnl > 0:
                    stats['win_count'] += 1
                    winning_trades.append(pnl)
                elif pnl < 0:
                    stats['loss_count'] += 1
                    losing_trades.append(pnl)

            except Exception as e:
                logger.error(f"Error processing trade {trade.id}: {str(e)}")
                continue

        # Update stats
        stats['total_profit'] = round(total_profit, 2)

        # Calculate win rate
        total_evaluated = stats['win_count'] + stats['loss_count'] 
        if total_evaluated > 0:
            stats['win_rate'] = round((stats['win_count'] / total_evaluated) * 100, 2)

        # Calculate average win/loss
        if winning_trades:
            stats['avg_win'] = round(sum(winning_trades) / len(winning_trades), 2)

        if losing_trades:
            stats['avg_loss'] = round(sum(losing_trades) / len(losing_trades), 2)

        # Calculate profit factor
        total_wins = sum(winning_trades) if winning_trades else 0
        total_losses = abs(sum(losing_trades)) if losing_trades else 0

        if total_losses > 0:
            stats['profit_factor'] = round(total_wins / total_losses, 2)
        elif total_wins > 0:
            stats['profit_factor'] = float('inf')  # No losses but has wins

        # Calculate drawdown
        try:
            # Sort trades by closed_at date, handling potential None values
            sorted_trades = sorted(
                [t for t in filtered_trades if t.pnl is not None and t.closed_at is not None],
                key=lambda t: t.closed_at
            )

            running_balance = 0
            peak_balance = 0
            max_drawdown = 0

            for trade in sorted_trades:
                running_balance += trade.pnl

                if running_balance > peak_balance:
                    peak_balance = running_balance

                drawdown = peak_balance - running_balance
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            stats['max_drawdown'] = round(max_drawdown, 2)
        except Exception as e:
            logger.error(f"Error calculating drawdown: {str(e)}")
            stats['max_drawdown'] = 0.0

        return jsonify(stats)
    except Exception as e:
        # Log error and return default stats with error info
        logger.error(f"Error calculating trade stats: {str(e)}")
        return jsonify({
            'total_trades': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'total_profit': 0.0,
            'max_drawdown': 0.0,
            'error': str(e)
        })

@app.route('/api/signals/current', methods=['GET'])
def get_current_signals():
    # ----- cursor params -------------------------------------------------
    limit  = min(request.args.get("limit", 25, int), 100)   # hard-cap
    cursor = request.args.get("cursor", type=int)           # id of *last* row client has

    q = (db.session.query(Signal)
            .filter(Signal.status.notin_([SignalStatus.EXPIRED, SignalStatus.CANCELLED, SignalStatus.ERROR])))

    if cursor:                               # “load more” call
        q = q.filter(Signal.id < cursor)     # everything *older* than the last id

    rows = q.order_by(Signal.id.desc()).limit(limit + 1).all()   # fetch one extra
    has_more   = len(rows) > limit
    nextCursor = rows[-1].id if has_more else None
    rows       = rows[:limit]                                   # strip the extra row

    return jsonify({
        "signals":   [r.to_dict() for r in rows],
        "hasMore":   has_more,
        "nextCursor": nextCursor
    })

@app.route('/api/signals/<int:signal_id>/cancel', methods=['POST'])
def cancel_signal(signal_id):
    signal = db.session.query(Signal).get(signal_id)
    if not signal:
        return jsonify({"status": "error", "message": f"Signal with ID {signal_id} not found"}), 404

    signal.status = SignalStatus.CANCELLED
    db.session.commit()

    return jsonify({"status": "success", "message": f"Signal {signal_id} cancelled successfully"})

@app.route('/api/settings/<section>', methods=['GET'])
def get_settings(section):
    # Get all settings for the section
    settings = Settings.get_section(section)
    return jsonify(settings)

@app.route('/api/settings/<section>', methods=['POST'])
def update_settings(section):
    # Update settings for the section
    settings_data = request.json
    if not settings_data:
        return jsonify({"error": "No settings data provided"}), 400

    for key, value in settings_data.items():
        Settings.set_value(section, key, value)

    return jsonify({"status": "success"})

@app.route('/api/ea-version', methods=['GET'])
def get_ea_version():
    # Get the current EA version
    return jsonify({
        "version": "1.0.5",
        "release_date": "2025-05-01",
        "changelog": "Fixed connection issues with MT5 terminal"
    })

# OANDA API Routes
@app.route('/api/oanda/account', methods=['GET'])
def get_oanda_account():
    """Get OANDA account information"""
    account_info = oanda_service.account_info()
    if not account_info:
        return jsonify({"error": "Unable to retrieve account information"}), 400
    return jsonify(account_info)

@app.route('/api/oanda/instruments', methods=['GET'])
def get_oanda_instruments():
    """Get available instruments from OANDA"""
    instruments = oanda_service.get_instruments()
    return jsonify(instruments)

@app.route('/api/oanda/candles/<instrument>', methods=['GET'])
@app.route('/api/candles/<instrument>', methods=['GET'])  # Add compatibility route for dashboard.js
def get_oanda_candles(instrument):
    """Get price candles for a specific instrument"""
    granularity = request.args.get('granularity', 'H1')
    count = request.args.get('count', 50, type=int)

    candles = oanda_service.get_candles(instrument, granularity, count)
    return jsonify(candles)

@app.route('/api/oanda/trades', methods=['GET'])
def get_oanda_trades():
    """Get open trades from OANDA"""
    trades = oanda_service.get_open_trades()
    return jsonify(trades)

@app.route('/api/oanda/test-connection', methods=['GET'])
def test_oanda_connection():
    """Test OANDA API connection"""
    is_connected = oanda_service.test_connection()
    return jsonify({"connected": is_connected})

@app.route('/api/mt5/heartbeat', methods=['GET'])
def get_mt5_heartbeat():
    """Get the latest MT5 heartbeat timestamp"""
    # Retrieve the latest heartbeat from the Settings table
    last_heartbeat = Settings.get_value('mt5', 'last_heartbeat', None)
    # Get connected terminals count
    connected_terminals = Settings.get_value('mt5', 'connected_terminals', 0)

    return jsonify({
        "last_heartbeat": last_heartbeat,
        "connected_terminals": connected_terminals
    })

# ---- Chart API Routes ----
@app.route('/api/charts/<symbol>', methods=['GET'])
def get_chart(symbol):
    """Generate and return a technical chart for a symbol"""
    from chart_utils import generate_chart_bytes

    # Get parameters from query string
    timeframe = request.args.get('timeframe', 'H1')
    count = request.args.get('count', 100, type=int)

    # Optional trade annotation parameters
    entry_time = request.args.get('entry_time')
    entry_price = request.args.get('entry_price', type=float)
    stop_loss = request.args.get('sl', type=float)
    take_profit = request.args.get('tp', type=float)
    result = request.args.get('result')  # 'win' or 'loss'

    # Set entry point if both time and price are provided
    entry_point = None
    if entry_time and entry_price:
        entry_point = (entry_time, entry_price)

    # Generate chart as bytes
    chart_bytes = generate_chart_bytes(
        symbol=symbol,
        timeframe=timeframe,
        count=count,
        entry_point=entry_point,
        stop_loss=stop_loss,
        take_profit=take_profit,
        result=result
    )

    if not chart_bytes:
        return jsonify({"error": "Failed to generate chart"}), 500

    # Create response with chart image
    response = make_response(chart_bytes)
    response.headers.set('Content-Type', 'image/png')
    return response

@app.route('/api/charts/download/<symbol>', methods=['GET'])
def download_chart(symbol):
    """Generate and download a technical chart for a symbol"""
    from chart_utils import generate_chart

    # Get parameters from query string
    timeframe = request.args.get('timeframe', 'H1')
    count = request.args.get('count', 100, type=int)

    # Optional trade annotation parameters
    entry_time = request.args.get('entry_time')
    entry_price = request.args.get('entry_price', type=float)
    stop_loss = request.args.get('sl', type=float)
    take_profit = request.args.get('tp', type=float)
    result = request.args.get('result')  # 'win' or 'loss'

    # Set entry point if both time and price are provided
    entry_point = None
    if entry_time and entry_price:
        entry_point = (entry_time, entry_price)

    # Generate and save chart
    chart_path = generate_chart(
        symbol=symbol,
        timeframe=timeframe,
        count=count,
        entry_point=entry_point,
        stop_loss=stop_loss,
        take_profit=take_profit,
        result=result
    )

    if not chart_path:
        return jsonify({"error": "Failed to generate chart"}), 500

    # Return the file for download with the exact filename from the chart path
    filename = os.path.basename(chart_path)
    return send_file(chart_path, as_attachment=True, download_name=filename)

@app.route('/charts')
def charts_page():
    """Charts page for generating technical analysis charts"""
    return render_template('charts.html')

@app.route('/api/mt5/account', methods=['GET'])
def get_mt5_account():
    """Get MT5 account information"""
    account_info = {
        'balance': Settings.get_value('mt5_account', 'balance', 0.0),
        'equity': Settings.get_value('mt5_account', 'equity', 0.0),
        'margin': Settings.get_value('mt5_account', 'margin', 0.0),
        'free_margin': Settings.get_value('mt5_account', 'free_margin', 0.0),
        'leverage': Settings.get_value('mt5_account', 'leverage', 1),
        'open_positions': Settings.get_value('mt5_account', 'open_positions', 0),
        'account_id': Settings.get_value('mt5_account', 'id', 'Not connected'),
        'last_update': Settings.get_value('mt5_account', 'last_update', None)
    }

    # Check if there's a recent update (within last 5 minutes)
    if account_info['last_update']:
        try:
            last_time = datetime.fromisoformat(account_info['last_update'])
            account_info['connected'] = (datetime.now() - last_time).total_seconds() < 300
        except:
            account_info['connected'] = False
    else:
        account_info['connected'] = False

    return jsonify(account_info)

# Register the MT5 API blueprint
from mt5_ea_api import mt5_api, api_routes
app.register_blueprint(mt5_api)
app.register_blueprint(api_routes)

# Endpoints for capture and analysis jobs
@app.route('/api/capture/manual', methods=['POST'])
def manual_capture():
    """Manually trigger a capture job for a specific symbol"""
    data = request.json
    symbol = data.get('symbol')

    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400

    try:
        import capture_job
        result = capture_job.run(symbol)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error running manual capture for {symbol}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/capture/status', methods=['GET'])
def get_capture_status():
    """Get status of capture and analysis jobs"""
    try:
        import redis
        try:
            redis_client = redis.Redis(
                host=os.environ.get('REDIS_HOST', 'localhost'),
                port=int(os.environ.get('REDIS_PORT', 6379)),
                db=int(os.environ.get('REDIS_DB', 0)),
                password=os.environ.get('REDIS_PASSWORD', None),
                decode_responses=True,
                socket_connect_timeout=1
            )

            vision_queue_length = redis_client.llen("vision_queue")
            signal_queue_length = redis_client.llen("signal_queue")

            return jsonify({
                "vision_queue_length": vision_queue_length,
                "signal_queue_length": signal_queue_length,
                "redis_connected": True
            })
        except redis.exceptions.ConnectionError as e:
            # Redis connection failed but system can still function
            logger.warning(f"Redis connection failed: {str(e)}")
            return jsonify({
                "vision_queue_length": 0,
                "signal_queue_length": 0,
                "redis_connected": False,
                "redis_message": f"Not connected: {str(e)}"
            })
    except Exception as e:
        logger.error(f"Error getting capture status: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Initialize tables and run app
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")

        # Start the scheduler
        try:
            from scheduler import start_scheduler
            scheduler = start_scheduler()
            logger.info("Capture scheduler started successfully")
        except Exception as e:
            logger.error(f"Error starting scheduler: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
