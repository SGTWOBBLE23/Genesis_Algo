from app import app, db, Signal, SignalStatus
import datetime

with app.app_context():
    # Recent signals
    recent_signals = Signal.query.filter(
        Signal.created_at > datetime.datetime.now() - datetime.timedelta(minutes=30)
    ).order_by(Signal.created_at.desc()).all()
    
    print(f"Recent signals (last 30 min): {len(recent_signals)}")
    
    # Count by status
    pending = Signal.query.filter_by(status=SignalStatus.PENDING.value).count()
    active = Signal.query.filter_by(status=SignalStatus.ACTIVE.value).count()
    triggered = Signal.query.filter_by(status=SignalStatus.TRIGGERED.value).count()
    cancelled = Signal.query.filter_by(status=SignalStatus.CANCELLED.value).count()
    
    print(f"Signal status counts:")
    print(f"  PENDING: {pending}")
    print(f"  ACTIVE: {active}")
    print(f"  TRIGGERED: {triggered}")
    print(f"  CANCELLED: {cancelled}")
    
    # Check latest signals
    if recent_signals:
        print("\nLatest 5 signals:")
        for i, signal in enumerate(recent_signals[:5]):
            context = signal.context if hasattr(signal, 'context') and callable(signal.context) else {}
            scoring = context.get('scoring', {}) if context else {}
            print(f"{i+1}. {signal.symbol} {signal.action} - Status: {signal.status}")
            print(f"   Confidence: {signal.confidence:.2f}")
            
            if scoring:
                technical_score = scoring.get('technical_score', 'N/A')
                ml_prob = scoring.get('technical_details', {}).get('ml_prob', 'N/A')
                print(f"   Technical Score: {technical_score}")
                print(f"   ML Probability: {ml_prob}")
