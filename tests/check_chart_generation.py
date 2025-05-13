from app import app
import os
import json
from datetime import datetime, timedelta

# Find the most recent signals and their associated charts
with app.app_context():
    # Get list of chart directories
    chart_base = os.path.join("static", "charts")
    chart_dirs = [d for d in os.listdir(chart_base) if os.path.isdir(os.path.join(chart_base, d))]
    
    print(f"Found chart directories: {chart_dirs}")
    
    # Get recent charts for XAUUSD
    recent_xau_charts = []
    xau_dir = os.path.join(chart_base, "XAUUSD")
    
    if os.path.exists(xau_dir):
        # Get all PNG files
        xau_files = [f for f in os.listdir(xau_dir) if f.endswith(".png")]
        
        # Sort by modification time (newest first)
        xau_files.sort(key=lambda x: os.path.getmtime(os.path.join(xau_dir, x)), reverse=True)
        
        # Get most recent 10
        recent_xau_charts = xau_files[:10]
    
    print(f"\nMost recent XAU charts:")
    for i, chart in enumerate(recent_xau_charts):
        mtime = datetime.fromtimestamp(os.path.getmtime(os.path.join(xau_dir, chart)))
        print(f"{i+1}. {chart} (Modified: {mtime})")
        
        # Check if the filename contains timeframe
        if "_M15_" in chart:
            print(f"   Timeframe: M15")
        elif "_H1_" in chart:
            print(f"   Timeframe: H1")
        else:
            print(f"   Timeframe: Unknown")
