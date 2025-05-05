#!/usr/bin/env python3

from app import app, db, Signal, SignalStatus, SignalAction
import json
from datetime import datetime

with app.app_context():
    # Create a signal with ultra-high confidence to test override
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
            'rsi': 25,  # Oversold condition
            'macd': 0.001,
            'macd_signal': -0.001,
            'timeframe': 'H1'
        })
    )
    
    # Add and commit
    db.session.add(signal)
    db.session.commit()
    
    print(f'Created signal with ID: {signal.id}')
