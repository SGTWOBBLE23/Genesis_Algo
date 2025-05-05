#!/usr/bin/env python3

from app import app, db, Signal, SignalStatus, SignalAction
import json
from datetime import datetime

with app.app_context():
    # Create a signal with ultra-high confidence to test override
    # This uses EURUSD which is in the restricted list
    signal = Signal(
        symbol='EUR_USD',
        action=SignalAction.ANTICIPATED_LONG,
        entry=1.135,
        sl=1.130,
        tp=1.140,
        confidence=0.99,
        status=SignalStatus.PENDING,
        context_json=json.dumps({
            'created_at': datetime.now().isoformat(),
            'rsi': 25,
            'macd': 0.001,
            'macd_signal': -0.001,
            'timeframe': 'H1',
            'comment': 'Ultra high confidence signal to test override',
            # Reset last_signal_id to 0 to force signal check
            'reset_last_signal_id': True
        })
    )
    
    # Add and commit
    db.session.add(signal)
    db.session.commit()
    
    print(f'Created signal with ID: {signal.id}')
    print('\nNow force-reset the signal ID with:')
    print("curl -X POST -H 'Content-Type: application/json' -d '{\"account_id\":\"163499\",\"last_signal_id\":0,\"reset_signals\":true,\"symbols\":[\"EURUSD\",\"GBPUSD\",\"USDJPY\",\"XAUUSD\",\"GBPJPY\"]}' http://localhost:5000/mt5/get_signals")
