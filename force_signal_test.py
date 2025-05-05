import os
import json
import logging
import uuid
from datetime import datetime

import redis
from flask import Flask
from app import db, Signal, SignalAction, SignalStatus

from chart_utils import generate_chart_bytes
from oanda_api import OandaAPI
from vision_worker import analyze_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis connection
try:
    redis_client = redis.Redis(
        host=os.environ.get('REDIS_HOST', 'localhost'),
        port=int(os.environ.get('REDIS_PORT', 6379)),
        db=int(os.environ.get('REDIS_DB', 0)),
        password=os.environ.get('REDIS_PASSWORD', None),
        decode_responses=True
    )
except Exception as e:
    logger.warning(f"Could not connect to Redis: {e}")
    redis_client = None

# OANDA API client
oanda_api = OandaAPI(
    api_key=os.environ.get('OANDA_API_KEY'),
    account_id=os.environ.get('OANDA_ACCOUNT_ID')
)

# Test assets
TEST_ASSETS = [
    "EUR_USD",
    "GBP_USD",
    "USD_JPY",
    "USD_CAD",
    "XAU_USD",
    "GBP_JPY"
]

def get_quote(symbol):
    """Fetch the current quote for a symbol from OANDA"""
    try:
        # Get current price from OANDA
        response = oanda_api._make_request(f"/instruments/{symbol}/candles?count=1&price=BA&granularity=M1")
        if not response or 'candles' not in response or not response['candles']:
            logger.error(f"Failed to get quote for {symbol}")
            return {}
            
        candle = response['candles'][0]
        bid = float(candle['bid']['c'])
        ask = float(candle['ask']['c'])
        spread = ask - bid
        timestamp = candle['time']
        
        return {
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "timestamp": timestamp
        }
    except Exception as e:
        logger.error(f"Error getting quote for {symbol}: {str(e)}")
        return {}

def force_signal_generation(symbol):
    """Force signal generation for a symbol"""
    # 1. Generate a chart for the symbol
    logger.info(f"Generating chart for {symbol}")
    image_bytes = generate_chart_bytes(symbol)
    
    # 2. Get current quote
    logger.info(f"Getting quote for {symbol}")
    quote = get_quote(symbol)
    if not quote:
        logger.error(f"Failed to get quote for {symbol}")
        return None
    
    # 3. Prepare metadata for vision analysis
    image_s3 = f"charts/{symbol}/{uuid.uuid4()}.png"
    
    # 4. Do vision analysis directly (bypass Redis queue)
    logger.info(f"Analyzing chart for {symbol}")
    vision_result = analyze_image(image_s3)
    
    if not vision_result or 'action' not in vision_result:
        logger.error(f"Failed to analyze chart for {symbol}")
        return None
        
    # 5. Create a signal from the vision result
    logger.info(f"Vision result for {symbol}: {vision_result}")
    
    # 6. Map the action string to SignalAction enum
    action_str = vision_result.get('action')
    if action_str is None:
        logger.error("Action is missing from vision result")
        return None
    
    try:
        signal_action = SignalAction[action_str]
    except KeyError:
        logger.error(f"Invalid action: {action_str}")
        # If we can't map it directly, try to find a close match
        if 'BUY' in action_str:
            signal_action = SignalAction.BUY_NOW
        elif 'SELL' in action_str:
            signal_action = SignalAction.SELL_NOW
        elif 'LONG' in action_str:
            signal_action = SignalAction.ANTICIPATED_LONG
        elif 'SHORT' in action_str:
            signal_action = SignalAction.ANTICIPATED_SHORT
        else:
            return None
        
    # Create signal in database
    signal = Signal(
        symbol=symbol,
        action=signal_action,
        entry=vision_result.get('entry'),
        sl=vision_result.get('sl'),
        tp=vision_result.get('tp'),
        confidence=vision_result.get('confidence'),
        status=SignalStatus.ACTIVE,  # Set to ACTIVE to make it available immediately
        context_json=json.dumps({
            'force_execution': True,
            'vision_result': vision_result,
            'quote': quote,
            'created_at': datetime.now().isoformat()
        })
    )
    
    # Save to database
    db.session.add(signal)
    db.session.commit()
    logger.info(f"Created signal {signal.id} for {symbol}")
    
    return signal

def main():
    # Initialize Flask app to get db context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Use existing db from app.py
    with app.app_context():
        # Process each test asset
        for symbol in TEST_ASSETS:
            logger.info(f"Processing {symbol}")
            signal = force_signal_generation(symbol)
            if signal:
                logger.info(f"Successfully generated signal {signal.id} for {symbol}")
            else:
                logger.error(f"Failed to generate signal for {symbol}")

if __name__ == "__main__":
    main()
