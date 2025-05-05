#!/usr/bin/env python3

"""
Signal Scoring Enhancement

This script updates the signal scoring implementation to ensure that high-confidence signals
(>=0.95 confidence) can bypass correlation checks and be executed even if there are too many
signals for a particular symbol.
"""

from app import app, db, Signal, SignalStatus, SignalAction
import json
from datetime import datetime

with app.app_context():
    # 1. Create a high-confidence signal to test the fix
    signal = Signal(
        symbol='EUR_USD',
        action=SignalAction.ANTICIPATED_LONG,
        entry=1.135,
        sl=1.130,
        tp=1.140,
        confidence=0.99,  # Ultra high confidence to override correlation
        status=SignalStatus.PENDING,
        context_json=json.dumps({
            'created_at': datetime.now().isoformat(),
            'rsi': 25,  # Oversold condition which should give +0.05 adjustment
            'macd': 0.001,
            'macd_signal': -0.001,  # Bullish crossover which should give another +0.05
            'timeframe': 'H1',
            'mt5_symbol': 'EURUSD',  # Explicitly define MT5 symbol
            'override_correlation': True  # Force override
        })
    )
    
    # Add and commit
    db.session.add(signal)
    db.session.commit()
    
    print(f'Created signal with ID: {signal.id}')
    print(f'Use this curl command to check if the signal is picked up:')
    print("curl -X POST -H 'Content-Type: application/json' -d '{\"account_id\":\"163499\",\"last_signal_id\":0,\"symbols\":[\"EURUSD\"]}' http://localhost:5000/mt5/get_signals")
