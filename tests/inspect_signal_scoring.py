from app import app, db, Signal, SignalStatus
import datetime
import json

with app.app_context():
    # Get a recent cancelled signal to analyze what's happening
    recent_signal = Signal.query.filter_by(status=SignalStatus.CANCELLED.value).order_by(Signal.created_at.desc()).first()
    
    if recent_signal:
        print(f"Analyzing recent cancelled signal:")
        print(f"Symbol: {recent_signal.symbol}")
        print(f"Action: {recent_signal.action}")
        print(f"Confidence: {recent_signal.confidence}")
        print(f"Created: {recent_signal.created_at}")
        
        # Extract and analyze the context JSON
        try:
            if hasattr(recent_signal, 'context') and callable(recent_signal.context):
                context = recent_signal.context
                print("\nContext data:")
                
                # Look for scoring information
                if 'scoring' in context:
                    scoring = context['scoring']
                    print(f"\nScoring details:")
                    
                    # Decision and reason
                    if 'decision' in scoring:
                        print(f"Decision: {scoring['decision']}")
                    if 'reason' in scoring:
                        print(f"Reason: {scoring['reason']}")
                    
                    # Technical score details
                    if 'technical_score' in scoring:
                        print(f"Technical score: {scoring['technical_score']}")
                    
                    # ML probability
                    if 'technical_details' in scoring and 'ml_prob' in scoring['technical_details']:
                        print(f"ML probability: {scoring['technical_details']['ml_prob']}")
                    
                    # Confidence threshold
                    if 'adjusted_confidence_threshold' in scoring:
                        print(f"Adjusted confidence threshold: {scoring['adjusted_confidence_threshold']}")
                    
                    # Component scores if available
                    if 'technical_details' in scoring and 'component_scores' in scoring['technical_details']:
                        print("\nComponent scores:")
                        for key, value in scoring['technical_details']['component_scores'].items():
                            print(f"  {key}: {value}")
            else:
                # Try to parse the context_json directly if available
                if hasattr(recent_signal, 'context_json') and recent_signal.context_json:
                    context = json.loads(recent_signal.context_json)
                    print(f"\nRaw context JSON: {json.dumps(context, indent=2)}")
        
        except Exception as e:
            print(f"Error analyzing context: {str(e)}")
    else:
        print("No recent cancelled signals found")
