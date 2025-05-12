from app import app, db, Signal
import json
import os
from datetime import datetime

with app.app_context():
    # Get a few recent signals
    recent = Signal.query.order_by(Signal.created_at.desc()).limit(5).all()
    
    for signal in recent:
        print(f"\nSignal: {signal.symbol} {signal.action} ({signal.created_at})")
        print(f"  Status: {signal.status}")
        
        # Try to extract image path from context
        if hasattr(signal, "context_json") and signal.context_json:
            try:
                context = json.loads(signal.context_json)
                if "image_path" in context:
                    img_path = context["image_path"]
                    print(f"  Image path: {img_path}")
                    
                    # Check if file exists
                    if os.path.exists(img_path):
                        # Check if this is an M15 or H1 chart
                        if "M15" in img_path:
                            print(f"  15-minute chart captured at {signal.created_at}")
                        elif "H1" in img_path:
                            print(f"  1-hour chart captured at {signal.created_at}")
                        
                        # Check file modification time
                        mtime = datetime.fromtimestamp(os.path.getmtime(img_path))
                        print(f"  File last modified: {mtime}")
                    else:
                        print(f"  Image file does not exist!")
                else:
                    print("  No image path in context")
            except Exception as e:
                print(f"  Error parsing context: {str(e)}")
    
    # Check the most recent M15 and H1 signals specifically for XAU_USD
    print("\n\nXAU_USD SIGNALS:")
    
    xau_m15 = Signal.query.filter_by(symbol="XAU_USD").order_by(Signal.created_at.desc()).all()
    m15_found = False
    h1_found = False
    
    for signal in xau_m15:
        if hasattr(signal, "context_json") and signal.context_json:
            try:
                context = json.loads(signal.context_json)
                if "image_path" in context:
                    img_path = context["image_path"]
                    
                    if "M15" in img_path and not m15_found:
                        print(f"Most recent M15 XAU_USD signal:")
                        print(f"  Created: {signal.created_at}")
                        print(f"  Status: {signal.status}")
                        print(f"  Image: {img_path}")
                        m15_found = True
                    
                    if "H1" in img_path and not h1_found:
                        print(f"Most recent H1 XAU_USD signal:")
                        print(f"  Created: {signal.created_at}")
                        print(f"  Status: {signal.status}")
                        print(f"  Image: {img_path}")
                        h1_found = True
                        
                    if m15_found and h1_found:
                        break
            except:
                continue
