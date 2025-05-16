#!/usr/bin/env python3
"""
Script to check which currency pairs are currently active in the system
"""
import os
import sys
import logging
from app import app, db, Signal, Trade, TradeStatus
from ml.exit_inference import _load_exit
from config import ASSETS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with app.app_context():
    # Check available exit models
    logger.info("\n== AVAILABLE EXIT MODELS ==")
    available_models = {}
    
    for symbol in ASSETS:
        # Convert OANDA format to MT5 format
        mt5_symbol = symbol.replace('_', '')
        
        # Check H1 models
        h1_model = _load_exit(mt5_symbol, "H1")
        available_models[f"{mt5_symbol}_H1"] = h1_model is not None
        
        # Check M15 models
        m15_model = _load_exit(mt5_symbol, "M15")
        available_models[f"{mt5_symbol}_M15"] = m15_model is not None
    
    for model_name, available in available_models.items():
        logger.info(f"{model_name}: {'Available' if available else 'Missing'}")
    
    # Check signal distribution
    logger.info("\n== SIGNAL COUNT BY SYMBOL ==")
    signals_by_symbol = db.session.query(Signal.symbol, db.func.count(Signal.id)).group_by(Signal.symbol).all()
    
    for symbol, count in signals_by_symbol:
        logger.info(f"{symbol}: {count} signals")
    
    # Check trade distribution
    logger.info("\n== TRADE COUNT BY SYMBOL ==")
    trades_by_symbol = db.session.query(Trade.symbol, db.func.count(Trade.id)).group_by(Trade.symbol).all()
    
    for symbol, count in trades_by_symbol:
        logger.info(f"{symbol}: {count} trades")
    
    # Check open trades
    logger.info("\n== OPEN TRADES BY SYMBOL ==")
    open_trades_by_symbol = db.session.query(Trade.symbol, db.func.count(Trade.id)).filter_by(status=TradeStatus.OPEN).group_by(Trade.symbol).all()
    
    for symbol, count in open_trades_by_symbol:
        logger.info(f"{symbol}: {count} open trades")
    
    # Check signal scoring thresholds
    logger.info("\n== SIGNAL SCORING DETAILS ==")
    try:
        import signal_scoring
        logger.info(f"Base technical score threshold: {signal_scoring.min_technical_score}")
        
        # Get recent signal scores
        recent_signals = db.session.query(Signal).order_by(Signal.id.desc()).limit(20).all()
        logger.info("\nRecent signal scores:")
        
        for signal in recent_signals:
            context = signal.context
            tech_score = context.get('technical_score', 'N/A') if context else 'N/A'
            logger.info(f"Signal {signal.id} ({signal.symbol}): Action={signal.action}, Confidence={signal.confidence}, Tech Score={tech_score}")
        
    except Exception as e:
        logger.error(f"Error checking signal scoring: {e}")