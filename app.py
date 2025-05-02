import os
import logging
import enum
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Union

from flask import Flask, render_template, request, jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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
    context_json = db.Column(db.Text, nullable=True)  # Additional trade context
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
    return render_template('index.html', title='Dashboard')

@app.route('/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/history')
def history():
    return render_template('history.html', title='Trading History')

@app.route('/settings')
def settings():
    return render_template('settings.html', title='Settings')

# API Routes
@app.route('/api/trades', methods=['GET'])
def get_trades():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 50, type=int)
    status = request.args.get('status')
    symbol = request.args.get('symbol')
    side = request.args.get('side')
    
    query = db.session.query(Trade)
    
    # Apply filters if provided
    if status:
        query = query.filter(Trade.status == TradeStatus(status))
    if symbol:
        query = query.filter(Trade.symbol == symbol)
    if side:
        query = query.filter(Trade.side == TradeSide(side))
    
    # Get total count for pagination
    total = query.count()
    pages = (total + limit - 1) // limit
    
    # Apply pagination
    trades = query.order_by(Trade.created_at.desc()).limit(limit).offset((page - 1) * limit).all()
    
    # Convert to dictionaries
    trade_list = [trade.to_dict() for trade in trades]
    
    return jsonify({
        'data': trade_list,
        'page': page,
        'limit': limit,
        'total': total,
        'pages': pages
    })

@app.route('/api/signals/current', methods=['GET'])
def get_current_signals():
    signals = db.session.query(Signal).filter(
        Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
    ).order_by(Signal.created_at.desc()).all()
    
    return jsonify([signal.to_dict() for signal in signals])

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

# Initialize tables and run app
# Register the MT5 API blueprint
from mt5_ea_api import mt5_api
app.register_blueprint(mt5_api)

# Initialize tables and run app
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {str(e)}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
