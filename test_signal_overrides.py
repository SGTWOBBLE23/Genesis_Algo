#!/usr/bin/env python3

"""
Signal Scoring System Demonstration

This script demonstrates the three layers of the signal scoring system:
1. Technical Filter Layer: Using RSI and MACD to adjust confidence
2. Performance-Based Adjustment: Boosting confidence based on recent performance
3. Correlation Analysis: Avoiding conflicting positions with high correlation

It also shows the high-confidence override feature that allows exceptional 
signals (>=0.95 confidence) to bypass correlation checks.
"""

from app import app, db, Signal, SignalStatus, SignalAction
import json
from datetime import datetime
import random
import time

# List of available symbols
symbols = ['EUR_USD', 'GBP_USD', 'USD_JPY', 'XAU_USD', 'GBP_JPY']

# Action types
actions = [SignalAction.ANTICIPATED_LONG, SignalAction.ANTICIPATED_SHORT]

def create_signal(symbol, action, confidence, include_technical=True):
    """Helper function to create signals with various confidence levels"""
    
    # Generate appropriate price levels
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
    
    # Set entry, SL, and TP based on action
    if action == SignalAction.ANTICIPATED_LONG:
        entry = price
        sl = round(price - (0.005 if symbol != 'XAU_USD' else 10.0), 
                   3 if symbol != 'XAU_USD' else 2)
        tp = round(price + (0.010 if symbol != 'XAU_USD' else 20.0), 
                   3 if symbol != 'XAU_USD' else 2)
        # For long positions, set RSI and MACD favorable for buys
        rsi = random.randint(20, 30) if include_technical else 50
        macd = 0.001 if include_technical else 0
        macd_signal = -0.001 if include_technical else 0
    else:  # SHORT
        entry = price
        sl = round(price + (0.005 if symbol != 'XAU_USD' else 10.0), 
                   3 if symbol != 'XAU_USD' else 2)
        tp = round(price - (0.010 if symbol != 'XAU_USD' else 20.0), 
                   3 if symbol != 'XAU_USD' else 2)
        # For short positions, set RSI and MACD favorable for sells
        rsi = random.randint(70, 80) if include_technical else 50
        macd = -0.001 if include_technical else 0
        macd_signal = 0.001 if include_technical else 0
        
    # Create signal with specified confidence
    signal = Signal(
        symbol=symbol,
        action=action,
        entry=entry,
        sl=sl,
        tp=tp,
        confidence=confidence,
        status=SignalStatus.PENDING,
        context_json=json.dumps({
            'created_at': datetime.now().isoformat(),
            'rsi': rsi,
            'macd': macd,
            'macd_signal': macd_signal,
            'timeframe': 'H1',
            'mt5_symbol': symbol.replace('_', ''),
            'override_correlation': confidence >= 0.95  # Force override for high confidence
        })
    )
    
    # Add to database
    db.session.add(signal)
    db.session.commit()
    
    return signal


def demonstrate_signal_scoring():
    signals = []
    
    # 1. Create a signal with moderate confidence (0.7) including technical indicators
    #    This should get a 0.1 boost from technical indicators but still be below the threshold
    s1 = create_signal('EUR_USD', SignalAction.ANTICIPATED_LONG, 0.7, include_technical=True)
    signals.append(s1)
    
    # 2. Create a signal with good confidence (0.8) but without technical indicators
    #    This should get no boost and remain at 0.8
    s2 = create_signal('GBP_USD', SignalAction.ANTICIPATED_SHORT, 0.8, include_technical=False)
    signals.append(s2)
    
    # 3. Create a signal with neutral confidence (0.85) with technical indicators
    #    This should get a 0.1 boost, pushing it to 0.95 which is the override threshold
    s3 = create_signal('USD_JPY', SignalAction.ANTICIPATED_LONG, 0.85, include_technical=True)
    signals.append(s3)
    
    # 4. Create a high confidence signal (0.98) with technical indicators
    #    This should reach 1.08 and override any correlation checks
    s4 = create_signal('GBP_JPY', SignalAction.ANTICIPATED_SHORT, 0.98, include_technical=True)
    signals.append(s4)
    
    # Display created signals
    print("\nCreated signals for scoring demonstration:")
    for signal in signals:
        print(f"  Signal {signal.id}: {signal.symbol} {signal.action} with confidence {signal.confidence}")
    
    # Provide curl commands to test these signals
    print("\nTest the signal with highest confidence to verify override functionality:")
    print(f"curl -X POST -H 'Content-Type: application/json' -d '{{\"account_id\":\"163499\",\"last_signal_id\":0,\"symbols\":[\"{signals[-1].symbol.replace('_', '')}\"]}}' http://localhost:5000/mt5/get_signals")
    

if __name__ == "__main__":
    with app.app_context():
        demonstrate_signal_scoring()
