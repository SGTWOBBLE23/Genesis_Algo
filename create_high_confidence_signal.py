#!/usr/bin/env python3

"""
High Confidence Signal Creator

This script demonstrates how to create a signal with high confidence (>=0.95)
that will bypass correlation checks in the signal scoring system.

Features:
- Creates a signal with 0.98 confidence
- Adds technical indicators to boost the score further
- Sets explicit MT5 symbol format
- Forces override through context parameters
"""

from app import app, db, Signal, SignalStatus, SignalAction
import json
from datetime import datetime
import random

# List of available symbols
symbols = ['EUR_USD', 'GBP_USD', 'USD_JPY', 'XAU_USD', 'GBP_JPY']

# Action types
actions = [SignalAction.ANTICIPATED_LONG, SignalAction.ANTICIPATED_SHORT]

def create_high_confidence_signal():
    with app.app_context():
        # 1. Select random symbol and action
        symbol = random.choice(symbols)
        action = random.choice(actions)
        
        # 2. Generate realistic price levels
        base_price = 0
        if symbol == 'EUR_USD':
            base_price = 1.135
        elif symbol == 'GBP_USD':
            base_price = 1.325
        elif symbol == 'USD_JPY':
            base_price = 144.25
        elif symbol == 'XAU_USD':
            base_price = 3320.00
        elif symbol == 'GBP_JPY':
            base_price = 191.50
            
        # Apply random offset
        offset = round(random.uniform(-0.5, 0.5) * (0.01 if symbol != 'XAU_USD' else 5.0), 
                       2 if symbol != 'XAU_USD' else 2)
        price = base_price + offset
        
        # 3. Set entry, SL, and TP based on action
        if action == SignalAction.ANTICIPATED_LONG:
            entry = price
            sl = round(price - (0.005 if symbol != 'XAU_USD' else 10.0), 
                       3 if symbol != 'XAU_USD' else 2)
            tp = round(price + (0.010 if symbol != 'XAU_USD' else 20.0), 
                       3 if symbol != 'XAU_USD' else 2)
            # For long positions, add oversold RSI
            rsi = random.randint(20, 30)
            macd = 0.001
            macd_signal = -0.001
        else:  # SHORT
            entry = price
            sl = round(price + (0.005 if symbol != 'XAU_USD' else 10.0), 
                       3 if symbol != 'XAU_USD' else 2)
            tp = round(price - (0.010 if symbol != 'XAU_USD' else 20.0), 
                       3 if symbol != 'XAU_USD' else 2)
            # For short positions, add overbought RSI
            rsi = random.randint(70, 80)
            macd = -0.001
            macd_signal = 0.001
            
        # 4. Create signal with high confidence
        signal = Signal(
            symbol=symbol,
            action=action,
            entry=entry,
            sl=sl,
            tp=tp,
            confidence=0.98,  # Ultra high confidence to override correlation
            status=SignalStatus.PENDING,
            context_json=json.dumps({
                'created_at': datetime.now().isoformat(),
                'rsi': rsi,
                'macd': macd,
                'macd_signal': macd_signal,
                'timeframe': 'H1',
                'mt5_symbol': symbol.replace('_', ''),  # Convert format for MT5
                'override_correlation': True  # Force override
            })
        )
        
        # 5. Add and commit
        db.session.add(signal)
        db.session.commit()
        
        return signal


if __name__ == "__main__":
    signal = create_high_confidence_signal()
    print(f"Created high-confidence signal:")
    print(f"  ID: {signal.id}")
    print(f"  Symbol: {signal.symbol}")
    print(f"  Action: {signal.action}")
    print(f"  Entry: {signal.entry}")
    print(f"  Stop Loss: {signal.sl}")
    print(f"  Take Profit: {signal.tp}")
    print(f"  Confidence: {signal.confidence}")
    print(f"\nTest with:")
    print(f"curl -X POST -H 'Content-Type: application/json' -d '{{\"account_id\":\"163499\",\"last_signal_id\":0,\"symbols\":[\"{signal.symbol.replace('_', '')}\"]}}' http://localhost:5000/mt5/get_signals")
