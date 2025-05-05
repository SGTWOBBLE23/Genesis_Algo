import os
import json
import logging
from datetime import datetime

from flask import Flask
from app import db, Signal, SignalAction, SignalStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_signals():
    """Create test trading signals for development and testing"""
    
    # Initialize Flask app to get db context
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    
    # Use existing db from app.py
    with app.app_context():
        # Create a BUY NOW signal for EUR_USD
        signal1 = Signal(
            symbol="EUR_USD",
            action=SignalAction.BUY_NOW,
            entry=1.13420,
            sl=1.13200,
            tp=1.13800,
            confidence=0.85,
            status=SignalStatus.ACTIVE,
            context_json=json.dumps({
                'force_execution': True,
                'created_at': datetime.now().isoformat()
            })
        )
        
        # Create an ANTICIPATED_LONG signal for GBP_USD
        signal2 = Signal(
            symbol="GBP_USD",
            action=SignalAction.ANTICIPATED_LONG,
            entry=1.45000,
            sl=1.44700,
            tp=1.45500,
            confidence=0.78,
            status=SignalStatus.ACTIVE,
            context_json=json.dumps({
                'force_execution': True,
                'created_at': datetime.now().isoformat()
            })
        )
        
        # Create a SELL_NOW signal for USD_JPY
        signal3 = Signal(
            symbol="USD_JPY",
            action=SignalAction.SELL_NOW,
            entry=156.750,
            sl=157.200,
            tp=156.000,
            confidence=0.82,
            status=SignalStatus.ACTIVE,
            context_json=json.dumps({
                'force_execution': True,
                'created_at': datetime.now().isoformat()
            })
        )
        
        # Create an ANTICIPATED_SHORT signal for USD_CAD
        signal4 = Signal(
            symbol="USD_CAD",
            action=SignalAction.ANTICIPATED_SHORT,
            entry=1.36800,
            sl=1.37100,
            tp=1.36300,
            confidence=0.75,
            status=SignalStatus.ACTIVE,
            context_json=json.dumps({
                'force_execution': True,
                'created_at': datetime.now().isoformat()
            })
        )
        
        # Create a BUY NOW signal for XAU_USD (Gold)
        signal5 = Signal(
            symbol="XAU_USD",
            action=SignalAction.BUY_NOW,
            entry=3450.00,
            sl=3430.00,
            tp=3490.00,
            confidence=0.89,
            status=SignalStatus.ACTIVE,
            context_json=json.dumps({
                'force_execution': True,
                'created_at': datetime.now().isoformat()
            })
        )
        
        # Create a signal for GBP_JPY
        signal6 = Signal(
            symbol="GBP_JPY",
            action=SignalAction.SELL_NOW,
            entry=225.500,
            sl=226.200,
            tp=224.300,
            confidence=0.80,
            status=SignalStatus.ACTIVE,
            context_json=json.dumps({
                'force_execution': True,
                'created_at': datetime.now().isoformat()
            })
        )
        
        # Save all signals to the database
        db.session.add(signal1)
        db.session.add(signal2)
        db.session.add(signal3)
        db.session.add(signal4)
        db.session.add(signal5)
        db.session.add(signal6)
        db.session.commit()
        
        logger.info(f"Created test signals with IDs: {signal1.id}, {signal2.id}, {signal3.id}, {signal4.id}, {signal5.id}, {signal6.id}")

if __name__ == "__main__":
    create_test_signals()
