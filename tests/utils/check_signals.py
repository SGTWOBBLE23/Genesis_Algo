import sys
from app import app, db, Signal, SignalStatus

with app.app_context():
    pending_signals = db.session.query(Signal).filter_by(status=SignalStatus.PENDING).count()
    active_signals = db.session.query(Signal).filter_by(status=SignalStatus.ACTIVE).count()
    triggered_signals = db.session.query(Signal).filter_by(status=SignalStatus.TRIGGERED).count()
    
    print(f"Pending signals: {pending_signals}")
    print(f"Active signals: {active_signals}")
    print(f"Triggered signals: {triggered_signals}")
    
    # Get most recent signals
    recent_signals = db.session.query(Signal).order_by(Signal.created_at.desc()).limit(5).all()
    print("\nMost recent signals:")
    for signal in recent_signals:
        print(f"ID: {signal.id}, Symbol: {signal.symbol}, Action: {signal.action}, Status: {signal.status}, Created: {signal.created_at}")