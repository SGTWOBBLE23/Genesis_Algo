#!/usr/bin/env python3
"""
Create a test signal for testing the signal filtering system
"""

import json
import sys
from datetime import datetime
from flask import jsonify
from app import app, db, Signal, SignalAction, SignalStatus

# Command-line arguments
if len(sys.argv) > 1:
    symbol = sys.argv[1]
else:
    symbol = "XAU_USD"

if len(sys.argv) > 2:
    action_str = sys.argv[2].upper()
    if action_str == "BUY":
        action = SignalAction.BUY_NOW
    elif action_str == "SELL":
        action = SignalAction.SELL_NOW
    elif action_str == "LONG":
        action = SignalAction.ANTICIPATED_LONG
    elif action_str == "SHORT":
        action = SignalAction.ANTICIPATED_SHORT
    else:
        print(f"Unknown action: {action_str}")
        print("Valid options: BUY, SELL, LONG, SHORT")
        sys.exit(1)
else:
    action = SignalAction.ANTICIPATED_SHORT

if len(sys.argv) > 3:
    try:
        confidence = float(sys.argv[3])
        if confidence < 0 or confidence > 1:
            raise ValueError("Confidence must be between 0.0 and 1.0")
    except ValueError as e:
        print(f"Invalid confidence value: {e}")
        sys.exit(1)
else:
    confidence = 0.8  # Default confidence

# Set up trade levels based on action
if symbol == "XAU_USD":
    current_price = 3200.00
    # Use small stop loss/take profit values for gold (in dollars)
    sl_distance = 50
    tp_distance = 100
elif symbol in ["USD_JPY", "EUR_JPY", "GBP_JPY"]:
    current_price = 150.00 if "USD" in symbol else 180.00
    # Use larger stops for JPY pairs (in pips)
    sl_distance = 1.0
    tp_distance = 2.0
else:
    current_price = 1.2000
    # Use standard forex stops (in pips)
    sl_distance = 0.0050
    tp_distance = 0.0100

if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG]:
    entry = current_price
    sl = current_price - sl_distance
    tp = current_price + tp_distance
else:  # SELL or SHORT
    entry = current_price
    sl = current_price + sl_distance
    tp = current_price - tp_distance

# Add technical indicator context for testing filter system
context = {
    "created_at": datetime.now().isoformat(),
    "rsi": 28 if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] else 75,
    "macd": 0.001 if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] else -0.001,
    "macd_signal": -0.001 if action in [SignalAction.BUY_NOW, SignalAction.ANTICIPATED_LONG] else 0.001,
    "timeframe": "H1",
    "comment": "Test signal with technical indicators for scoring system"
}

# Use application context for all database operations
with app.app_context():
    # Create the signal
    new_signal = Signal(
        symbol=symbol,
        action=action,
        entry=entry,
        sl=sl,
        tp=tp,
        confidence=confidence,
        status=SignalStatus.PENDING,
        context_json=json.dumps(context)
    )
    
    # Add to database
    db.session.add(new_signal)
    db.session.commit()
    
    # Get signal ID after commit
    signal_id = new_signal.id
    
    # Print signal details
    print(f"Created test signal:")
    print(f"ID: {signal_id}")
    print(f"Symbol: {new_signal.symbol}")
    print(f"Action: {new_signal.action}")
    print(f"Entry: {new_signal.entry}")
    print(f"Stop Loss: {new_signal.sl}")
    print(f"Take Profit: {new_signal.tp}")
    print(f"Confidence: {new_signal.confidence}")
    print(f"Status: {new_signal.status}")
    print(f"Context: {new_signal.context_json}")
print(f"\nNow test with:\ncurl -X POST -H 'Content-Type: application/json' -d '{{'account_id':'163499','last_signal_id':0,'symbols':['EURUSD','GBPUSD','USDJPY','XAUUSD','GBPJPY']}}' http://localhost:5000/mt5/get_signals")
