from app import app, db, Signal, SignalStatus
import datetime

with app.app_context():
    # Get most recent signals - last 5 minutes
    last_signals = Signal.query.filter(
        Signal.created_at > datetime.datetime.now() - datetime.timedelta(minutes=5)
    ).order_by(Signal.created_at.desc()).all()
    
    print(f"Signals in the last 5 minutes: {len(last_signals)}")
    
    # Check if any are not cancelled
    active_signals = [s for s in last_signals if s.status != SignalStatus.CANCELLED.value]
    print(f"Active signals in the last 5 minutes: {len(active_signals)}")
    
    # Print details of all recent signals
    print("\nLast signals details:")
    for i, signal in enumerate(last_signals[:5]):
        print(f"{i+1}. {signal.symbol} {signal.action} - Status: {signal.status}")
        print(f"   Created at: {signal.created_at}")
        print(f"   Confidence: {signal.confidence}")
        
        # Get context if available
        if hasattr(signal, 'context_json') and signal.context_json:
            import json
            try:
                context = json.loads(signal.context_json)
                if 'scoring' in context:
                    scoring = context['scoring']
                    if 'technical_score' in scoring:
                        print(f"   Technical score: {scoring['technical_score']}")
                    if 'technical_details' in scoring and 'ml_prob' in scoring['technical_details']:
                        print(f"   ML probability: {scoring['technical_details']['ml_prob']}")
                    if 'technical_details' in scoring and 'final_technical_score' in scoring['technical_details']:
                        print(f"   Final technical score: {scoring['technical_details']['final_technical_score']}")
            except Exception as e:
                print(f"   Error parsing context: {str(e)}")
