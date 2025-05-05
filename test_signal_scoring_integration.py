#!/usr/bin/env python3

"""
Test script for the signal scoring integration with MT5 API

This script creates test signals with different characteristics
and verifies that the scoring system correctly filters them.
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from app import db, Signal, SignalAction, SignalStatus
from signal_scoring import signal_scorer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_signal(symbol, action, confidence, entry=None, sl=None, tp=None):
    """Create a test signal with the given parameters"""
    signal = Signal(
        symbol=symbol,
        action=action,
        confidence=confidence,
        entry=entry,
        sl=sl,
        tp=tp,
        status=SignalStatus.PENDING,
        context_json=json.dumps({"test": True, "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
    )
    
    db.session.add(signal)
    db.session.commit()
    return signal

def test_signal_scoring():
    """Test the signal scoring system with various test signals"""
    logger.info("=== Testing Signal Scoring Integration ===")
    
    # Create test signals with various characteristics
    signals = [
        # Good signal - high confidence, good technical conditions
        create_test_signal(
            symbol="EUR_USD",
            action=SignalAction.BUY_NOW,
            confidence=0.85,
            entry=1.1325,
            sl=1.1300,
            tp=1.1375
        ),
        # Weak signal - low confidence
        create_test_signal(
            symbol="GBP_USD",
            action=SignalAction.SELL_NOW,
            confidence=0.55,  # Below threshold
            entry=1.4250,
            sl=1.4280,
            tp=1.4200
        ),
        # Correlated symbol test
        create_test_signal(
            symbol="EUR_JPY",
            action=SignalAction.SELL_NOW,
            confidence=0.75,
            entry=160.50,
            sl=161.00,
            tp=159.50
        ),
        # High risk anticipated trade
        create_test_signal(
            symbol="XAU_USD",
            action=SignalAction.ANTICIPATED_LONG,
            confidence=0.70,
            entry=3300.00,
            sl=3250.00,  # Wide stop loss
            tp=3350.00
        ),
    ]
    
    # Test each signal
    for i, signal in enumerate(signals, 1):
        logger.info(f"\nTesting Signal #{i}: {signal.symbol} {signal.action.name}, Confidence: {signal.confidence}")
        
        # Apply scoring system
        should_execute, details = signal_scorer.should_execute_signal(signal)
        
        # Log results
        if should_execute:
            logger.info(f"PASSED: Signal {signal.id} ({signal.symbol} {signal.action.name})")
            logger.info(f"Reason: {details['reason']}")
        else:
            logger.info(f"REJECTED: Signal {signal.id} ({signal.symbol} {signal.action.name})")
            logger.info(f"Reason: {details['reason']}")
        
        # Print key scoring details
        if 'technical_score' in details:
            logger.info(f"Technical Score: {details['technical_score']:.2f}")
        if 'adjustment_factor' in details:
            logger.info(f"Performance Adjustment: {details['adjustment_factor']:.2f}")
        if 'adjusted_confidence_threshold' in details:
            logger.info(f"Adjusted Confidence Threshold: {details['adjusted_confidence_threshold']:.2f}")
    
    logger.info("\n=== Test Completed ===")

if __name__ == "__main__":
    test_signal_scoring()
