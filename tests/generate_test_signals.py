#!/usr/bin/env python3

"""
Test Signal Generator

This script creates test trading signals for the 5 restricted asset pairs.
These signals will appear in the dashboard for testing purposes.
"""

import os
import json
import random
from datetime import datetime, timedelta

from app import app, db, Signal, SignalAction, SignalStatus

# The 5 asset pairs we're working with
SYMBOLS = ['XAU_USD', 'GBP_JPY', 'GBP_USD', 'EUR_USD', 'USD_JPY']

# Possible signal actions
ACTIONS = [
    SignalAction.BUY_NOW,
    SignalAction.SELL_NOW,
    SignalAction.ANTICIPATED_LONG,
    SignalAction.ANTICIPATED_SHORT
]

# Signal statuses to create
STATUSES = [
    SignalStatus.PENDING,
    SignalStatus.ACTIVE,
    SignalStatus.TRIGGERED,
    SignalStatus.ERROR
]

# Price ranges for each symbol (approximate)
PRICE_RANGES = {
    'XAU_USD': {'base': 2400.0, 'range': 50.0, 'digits': 2},  # Gold
    'GBP_JPY': {'base': 190.0, 'range': 2.0, 'digits': 3},     # British Pound to Japanese Yen
    'GBP_USD': {'base': 1.25, 'range': 0.02, 'digits': 5},     # British Pound to US Dollar
    'EUR_USD': {'base': 1.08, 'range': 0.02, 'digits': 5},     # Euro to US Dollar
    'USD_JPY': {'base': 155.0, 'range': 2.0, 'digits': 3}      # US Dollar to Japanese Yen
}

def generate_price(symbol, action=None):
    """Generate realistic prices for the given symbol"""
    price_info = PRICE_RANGES[symbol]
    base = price_info['base']
    price_range = price_info['range']
    digits = price_info['digits']
    
    # Base entry price with some randomness
    entry = round(base + (random.random() * 2 - 1) * price_range, digits)
    
    # Determine direction based on action
    is_buy = action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG]
    
    # Appropriate stop loss and take profit
    sl_range = price_range * 0.3  # 30% of the price range
    tp_range = price_range * 0.6  # 60% of the price range for 1:2 risk-reward
    
    if is_buy:
        sl = round(entry - sl_range, digits)
        tp = round(entry + tp_range, digits)
    else:
        sl = round(entry + sl_range, digits)
        tp = round(entry - tp_range, digits)
    
    return entry, sl, tp

def create_test_signal(symbol, action, status, entry=None, sl=None, tp=None):
    """Create a test signal with the given parameters"""
    if entry is None or sl is None or tp is None:
        entry, sl, tp = generate_price(symbol, action)
    
    # Context data for the signal
    context = {
        'source': 'test_generator',
        'created_at': datetime.now().isoformat(),
        'note': 'This is a test signal for dashboard display',
        'timeframe': random.choice(['M15', 'H1', 'H4']),
        'confidence_factors': [
            'EMA crossover',
            'RSI confirmation',
            'Support/resistance level'
        ]
    }
    
    # Create and add the signal to the database
    signal = Signal(
        symbol=symbol,
        action=action,
        entry=entry,
        sl=sl,
        tp=tp,
        confidence=round(random.uniform(0.6, 0.95), 2),
        status=status,
        context_json=json.dumps(context)
    )
    
    db.session.add(signal)
    return signal

# Main execution
if __name__ == '__main__':
    with app.app_context():
        created_count = 0
        try:
            # Check existing signals in the database
            existing_count = Signal.query.count()
            print(f"Database has {existing_count} existing signals")
            
            # Only proceed if fewer than 10 signals exist
            if existing_count < 10:
                # Create varied signals for each symbol
                for symbol in SYMBOLS:
                    # One pending signal (new)
                    signal = create_test_signal(
                        symbol=symbol,
                        action=random.choice([SignalAction.ANTICIPATED_LONG, SignalAction.ANTICIPATED_SHORT]),
                        status=SignalStatus.PENDING
                    )
                    created_count += 1
                    
                    # One active signal (ready for execution)
                    signal = create_test_signal(
                        symbol=symbol,
                        action=random.choice([SignalAction.BUY_NOW, SignalAction.SELL_NOW]),
                        status=SignalStatus.ACTIVE
                    )
                    created_count += 1
                    
                    # One error signal
                    signal = create_test_signal(
                        symbol=symbol,
                        action=random.choice(ACTIONS),
                        status=SignalStatus.ERROR
                    )
                    created_count += 1
                
                # Commit all the changes
                db.session.commit()
                print(f"Created {created_count} test signals successfully!")
            else:
                print("Database already has signals, skipping test signal creation.")
                print("Run reset_mt5_signals.py first if you want to clear existing signals.")
                
        except Exception as e:
            db.session.rollback()
            print(f"Error creating test signals: {str(e)}")
